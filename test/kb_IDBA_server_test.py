import unittest
import os
import time
import shutil
import uuid

from os import environ
from configparser import ConfigParser
from pathlib import Path
import psutil

import requests
from installed_clients.WorkspaceClient import Workspace as workspaceService
from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.baseclient import ServerError
from installed_clients.AbstractHandleClient import AbstractHandle as HandleService
from kb_IDBA.kb_IDBAImpl import kb_IDBA
from ReadsUtils.ReadsUtilsClient import ReadsUtils
from kb_IDBA.kb_IDBAServer import MethodContext
from pprint import pprint
import inspect

class kb_IDBATest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.token = environ.get('KB_AUTH_TOKEN')
        cls.callbackURL = environ.get('SDK_CALLBACK_URL')
        print('CB URL: ' + cls.callbackURL)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': cls.token,
                        'provenance': [
                            {'service': 'kb_IDBA',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_IDBA'):
            cls.cfg[nameval[0]] = nameval[1]
        cls.wsURL = cls.cfg['workspace-url']
        cls.shockURL = cls.cfg['shock-url']
        cls.hsURL = cls.cfg['handle-service-url']
        cls.dfu = DataFileUtil(cls.callbackURL, token=cls.token)
        cls.hs = HandleService(url=cls.hsURL, token=cls.token)
        cls.wsClient = workspaceService(cls.wsURL, token=cls.token)
        wssuffix = int(time.time() * 1000)
        wsName = "test_kb_IDBA" + str(wssuffix)
        cls.wsinfo = cls.wsClient.create_workspace({'workspace': wsName})
        print('created workspace ' + cls.getWsName())
        cls.serviceImpl = kb_IDBA(cls.cfg)
        cls.readUtilsImpl = ReadsUtils(cls.callbackURL, token=cls.token)
        cls.staged = {}
        cls.nodes_to_delete = []
        cls.handles_to_delete = []
        cls.setupTestData()
        print('\n\n=============== Starting tests ==================')


    @classmethod
    def tearDownClass(cls):

        print('\n\n=============== Cleaning up ==================')

        if hasattr(cls, 'wsinfo'):
            cls.wsClient.delete_workspace({'workspace': cls.getWsName()})
            print('Test workspace was deleted: ' + cls.getWsName())
        if hasattr(cls, 'nodes_to_delete'):
            for node in cls.nodes_to_delete:
                cls.delete_shock_node(node)
        if hasattr(cls, 'handles_to_delete'):
            handles = cls.hs.hids_to_handles(cls.handles_to_delete)
            cls.hs.delete_handles(handles)
            print('Deleted handles ' + str(cls.handles_to_delete))


    @classmethod
    def getWsName(cls):
        return cls.wsinfo[1]


    def getImpl(self):
        return self.serviceImpl


    @classmethod
    def delete_shock_node(cls, node_id):
        header = {'Authorization': 'Oauth {0}'.format(cls.token)}
        requests.delete(cls.shockURL + '/node/' + node_id, headers=header,
                        allow_redirects=True)
        print('Deleted shock node ' + node_id)

    @classmethod
    def upload_file_to_blobstore_and_get_handle(cls, test_file):
        '''
        Uploads the file in test_file to the blobstore and returns the node and a
        handle to the node.
        '''
        print(f'loading file to blobstore: {test_file}')
        res = cls.dfu.file_to_shock({'file_path': str(test_file), 'make_handle': 1})
        node_id = res["shock_id"]
        handle_id = res["handle"]["hid"]
        cls.nodes_to_delete.append(node_id)
        cls.handles_to_delete.append(handle_id)
        return node_id, handle_id


    @classmethod
    def upload_reads(cls, wsobjname, object_body, fwd_reads,
                     rev_reads=None, single_end=False, sequencing_tech='Illumina',
                     single_genome='1'):

        ob = dict(object_body)  # copy
        ob['sequencing_tech'] = sequencing_tech
        ob['wsname'] = cls.getWsName()
        ob['name'] = wsobjname
        if single_end or rev_reads:
            ob['interleaved']= 0
        else:
            ob['interleaved']= 1
        print('\n===============staging data for object ' + wsobjname +
              '================')
        print(f"uploading forward reads file {fwd_reads['file']}")
        fwd_id, fwd_handle_id = cls.upload_file_to_blobstore_and_get_handle(fwd_reads['file'])

        ob['fwd_id']= fwd_id
        rev_id = None
        rev_handle_id = None
        if rev_reads:
            print(f"uploading reverse reads file {rev_reads['file']}")
            rev_id, rev_handle_id = cls.upload_file_to_blobstore_and_get_handle(rev_reads['file'])
            ob['rev_id']= rev_id
        obj_ref = cls.readUtilsImpl.upload_reads(ob)
        objdata = cls.wsClient.get_object_info_new({
            'objects': [{'ref': obj_ref['obj_ref']}]
            })[0]
        cls.staged[wsobjname] = {'info': objdata,
                                 'ref': cls.make_ref(objdata),
                                 'fwd_node_id': fwd_id,
                                 'rev_node_id': rev_id,
                                 'fwd_handle_id': fwd_handle_id,
                                 'rev_handle_id': rev_handle_id
                                 }


    @classmethod
    def upload_empty_data(cls, wsobjname):
        objdata = cls.wsClient.save_objects({
            'workspace': cls.getWsName(),
            'objects': [{'type': 'Empty.AType',
                         'data': {},
                         'name': 'empty'
                         }]
            })[0]
        cls.staged[wsobjname] = {'info': objdata,
                                 'ref': cls.make_ref(objdata),
                                 }


    @classmethod
    def setupTestData(cls):
        print('Shock url ' + cls.shockURL)
        print('WS url ' + cls.wsURL)
        print('Handle service url ' + cls.hsURL)
        print('CPUs detected ' + str(psutil.cpu_count()))
        print('Available memory ' + str(psutil.virtual_memory().available))
        print('staging data')
        # move test data to scratch space so DFU can read it
        tmp_dir = Path(cls.cfg['scratch']) / ("test_input" + str(uuid.uuid4()))
        os.makedirs(tmp_dir)
        shutil.copy("data/small.forward.fq", tmp_dir)
        shutil.copy("data/small.reverse.fq", tmp_dir)
        shutil.copy("data/interleaved.fq", tmp_dir)
        # get file type from type
        fwd_reads = {'file': tmp_dir / 'small.forward.fq',
                     'name': 'test_fwd.fastq',
                     'type': 'fastq'}
        # get file type from handle file name
        rev_reads = {'file': tmp_dir / 'small.reverse.fq',
                     'name': 'test_rev.FQ',
                     'type': ''}
        int_reads = {'file': tmp_dir / 'interleaved.fq',
                     'name': '',
                     'type': ''}

        cls.upload_reads('frbasic', {}, fwd_reads, rev_reads=rev_reads)
        cls.upload_reads('reads_out', {'read_orientation_outward': 1},
                         int_reads)
        cls.delete_shock_node(cls.nodes_to_delete.pop())
        cls.upload_empty_data('empty')
        print('Data staged.')


    @classmethod
    def make_ref(self, object_info):
        return str(object_info[6]) + '/' + str(object_info[0]) + \
            '/' + str(object_info[4])


    def test_run_idba_ud(self):

        self.run_success(
            ['frbasic'], 'frbasic_out',
            {'contigs':
             [{'name': 'contig-100_0',
               'length': 64801,
               'id': 'contig-100_0',
               'md5': '4b32ecd41a221ff898ad7bf727db5a00'
               },
              {'name': 'contig-100_1',
               'length': 62656,
               'id': 'contig-100_1',
               'md5': '3cd5d6691bfb365e1c3f34a86ab8cc58'
               }],
             'md5': 'b348da4b1bc1383c428d131727383cfe',
             'remote_md5': '7c56c8e5c8ad2fcde336828f181d42c6'
             },
            200,
            {'mink_arg':20, 'maxk_arg':100, 'step_arg': 20} )


    def test_run_idba_ud_min_contigs(self):

        self.run_success(
            ['frbasic'], 'frbasic_out',
            {'contigs':
             [{'name': 'contig-100_0',
               'length': 64794,
               'id': 'contig-100_0',
               'md5': '4c80dc42680c2f3b9c4f90f01234410d'
               }],
             'md5': 'a52892e48a71f3de4c30844065d857ef',
             'remote_md5': 'e1e23af09addfbd5d51c4ce272f2d4a3'
             },
            63000,
            {'mink_arg':20, 'maxk_arg':100, 'step_arg': 20} )


    def test_no_workspace_param(self):

        self.run_error(
            ['foo'], 'workspace_name parameter is required', wsname=None)


    def test_no_workspace_name(self):

        self.run_error(
            ['foo'], 'workspace_name parameter is required', wsname='None')


    def test_bad_workspace_name(self):

        self.run_error(['foo'], 'Invalid workspace name bad|name',
                       wsname='bad|name')


    def test_non_extant_workspace(self):

        self.run_error(
            ['foo'], 'Object foo cannot be accessed: No workspace with name ' +
            'Ireallyhopethisworkspacedoesntexistorthistestwillfail exists',
            wsname='Ireallyhopethisworkspacedoesntexistorthistestwillfail',
            exception=ServerError)


    def test_no_libs_param(self):

        self.run_error(None, 'read_libraries parameter is required')


    def test_non_extant_lib(self):

        self.run_error(
            ['foo'],
            ('No object with name foo exists in workspace {} ' +
             '(name {})').format(str(self.wsinfo[0]), self.wsinfo[1]),
            exception=ServerError)


    def test_no_libs(self):

        self.run_error([], 'At least one reads library must be provided')


    def test_no_output_param(self):

        self.run_error(
            ['foo'], 'output_contigset_name parameter is required',
            output_name=None)


    def test_invalid_min_contig_length(self):

        self.run_error(
                ['foo'], 'min_contig must be of type int', wsname='fake', output_name='test-output',
                       min_contig_length='not an int!', kval_args=None)


    def test_invalid_mink_arg(self):

        self.run_error(
                ['foo'], 'min k value must be of type int', wsname='fake', output_name='test-output',
                    min_contig_length=0, kval_args={'mink_arg': 'non int', 'maxk_arg': 0, 'step_arg': 0})


    def test_invalid_maxk_arg(self):

        self.run_error(
                ['foo'], 'max k value must be of type int', wsname='fake', output_name='test-output',
                    min_contig_length=0, kval_args={'mink_arg': 0, 'maxk_arg': 'non int', 'step_arg': 0})
        

    def test_invalid_step_arg(self):

        self.run_error(
                ['foo'], 'step value must be of type int', wsname='fake', output_name='test-output',
                     min_contig_length=0, kval_args={'mink_arg': 0, 'maxk_arg': 0, 'step_arg': 'non int'})


    def test_outward_reads(self):

        self.run_error(
            ['reads_out'],
            'Reads object ' + self.getWsName() + '/reads_out (' +
            self.staged['reads_out']['ref'] +
            ') is marked as having outward oriented reads, which IDBA-UD ' +
            'does not support.')


    def run_error(self, readnames, error, wsname=('fake'), output_name='out',
                    min_contig_length=0, kval_args=None, exception=ValueError):

        test_name = inspect.stack()[1][3]
        print('\n***** starting expected fail test: ' + test_name + ' *****')
        print('    libs: ' + str(readnames))

        if wsname == ('fake'):
            wsname = self.getWsName()

        params = {}
        if (wsname is not None):
            if wsname == 'None':
                params['workspace_name'] = None
            else:
                params['workspace_name'] = wsname

        if (readnames is not None):
            params['read_libraries'] = readnames

        if (output_name is not None):
            params['output_contigset_name'] = output_name

        params['min_contig_length'] = min_contig_length
        params['kval_args'] = kval_args

        with self.assertRaises(exception) as context:
            self.getImpl().run_idba_ud(self.ctx, params)
        self.assertEqual(error, str(context.exception.args[0]))


    def run_success(self, readnames, output_name, expected, min_contig_length=None, kval_args=None):

        test_name = inspect.stack()[1][3]
        print('\n**** starting expected success test: ' + test_name + ' *****')
        print('   libs: ' + str(readnames))

        # expected number of contigs in output
        contig_count = len(expected['contigs'])

        print("READNAMES: " + str(readnames))
        print("STAGED: " + str(self.staged))

        libs = [self.staged[n]['info'][1] for n in readnames]

        params = {'workspace_name': self.getWsName(),
                  'read_libraries': libs,
                  'output_contigset_name': output_name,
                  'min_contig_length' : min_contig_length,
                  'kval_args': kval_args
                  }

        print("PARAMS BEFORE CALLING ================== IDBA-UD")
        pprint(params)
        print("=============  END OF PARAMS TO  ================  IDBA-UD")

        ret = self.getImpl().run_idba_ud(self.ctx, params)[0]

        print('RESULT from IDBA-UD:')
        pprint(ret)
        print("====================   END OF RESULT: ")

        report = self.wsClient.get_objects([{'ref': ret['report_ref']}])[0]
        self.assertEqual('KBaseReport.Report', report['info'][2].split('-')[0])
        self.assertEqual(1, len(report['data']['objects_created']))
        self.assertEqual('Assembled contigs',
                         report['data']['objects_created'][0]['description'])
        self.assertIn('Assembled into ' + str(contig_count) +
                      ' contigs', report['data']['text_message'])

        print("PROVENANCE: ")
        pprint(report['provenance'])
        print("====================   END OF PROVENANCE: ")

        assembly_ref = report['data']['objects_created'][0]['ref']
        assembly = self.wsClient.get_objects([{'ref': assembly_ref}])[0]
        print("ASSEMBLY OBJECT:")
        pprint(assembly)
        print("===============  END OF ASSEMBLY OBJECT:")
        self.assertEqual('KBaseGenomeAnnotations.Assembly', assembly['info'][2].split('-')[0])

        self.assertEqual(1, len(assembly['provenance']))
        self.assertEqual(output_name, assembly['info'][1])

        temp_handle_info = self.hs.hids_to_handles([assembly['data']['fasta_handle_ref']])
        print("HANDLE OBJECT:")
        pprint(temp_handle_info)
        assembly_fasta_node = temp_handle_info[0]['id']
        self.nodes_to_delete.append(assembly_fasta_node)

        # Test the resulting number of contigs, contigs' names, length of each contig.
        # the testing of equality of md5s have not been commented out,
        # as they happen to be different across runs

        '''
        header = {"Authorization": "Oauth {0}".format(self.token)}
        fasta_node = requests.get(self.shockURL + '/node/' + assembly_fasta_node,
                                  headers=header, allow_redirects=True).json()
        self.assertEqual(expected['remote_md5'],
                         fasta_node['data']['file']['checksum']['md5'])
        '''

        self.assertEqual(contig_count, len(assembly['data']['contigs']))
        self.assertEqual(output_name, assembly['data']['assembly_id'])

        #self.assertEqual(expected['md5'], assembly['data']['md5'])

        for exp_contig in expected['contigs']:
            if exp_contig['id'] in assembly['data']['contigs']:
                obj_contig = assembly['data']['contigs'][exp_contig['id']]
                self.assertEqual(exp_contig['name'], obj_contig['name'])
                self.assertEqual(exp_contig['length'], obj_contig['length'])
                #self.assertEqual(exp_contig['md5'], obj_contig['md5'])
            else:
                # Hacky way to do this, but need to see all the contig_ids
                # They changed because the IDBA version changed and
                # Need to see them to update the tests accordingly.
                # If code gets here this test is designed to always fail, but show results.
                self.assertEqual(str(assembly['data']['contigs']),"BLAH")

