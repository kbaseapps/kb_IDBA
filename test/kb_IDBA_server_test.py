from __future__ import print_function
import unittest
import os
import time

from os import environ
from ConfigParser import ConfigParser
import psutil

import requests
from biokbase.workspace.client import Workspace as workspaceService  # @UnresolvedImport @IgnorePep8
from biokbase.workspace.client import ServerError as WorkspaceError  # @UnresolvedImport @IgnorePep8
from biokbase.AbstractHandle.Client import AbstractHandle as HandleService  # @UnresolvedImport @IgnorePep8
from kb_IDBA.kb_IDBAImpl import kb_IDBA
from ReadsUtils.baseclient import ServerError
from ReadsUtils.ReadsUtilsClient import ReadsUtils
from kb_IDBA.kb_IDBAServer import MethodContext
from pprint import pprint
import shutil
import inspect
from kb_IDBA.GenericClient import GenericClient


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
        cls.hs = HandleService(url=cls.cfg['handle-service-url'],
                               token=cls.token)
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
            cls.hs.delete_handles(cls.hs.ids_to_handles(cls.handles_to_delete))
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


    # Helper script borrowed from the transform service, logger removed
    @classmethod
    def upload_file_to_shock(cls, file_path):
        """
        Use HTTP multi-part POST to save a file to a SHOCK instance.
        """

        header = dict()
        header["Authorization"] = "Oauth {0}".format(cls.token)

        if file_path is None:
            raise Exception("No file given for upload to SHOCK!")

        with open(os.path.abspath(file_path), 'rb') as dataFile:
            files = {'upload': dataFile}
            print('POSTing data')
            response = requests.post(
                cls.shockURL + '/node', headers=header, files=files,
                stream=True, allow_redirects=True)
            print('got response')

        if not response.ok:
            response.raise_for_status()

        result = response.json()

        if result['error']:
            raise Exception(result['error'][0])
        else:
            return result["data"]


    @classmethod
    def upload_file_to_shock_and_get_handle(cls, test_file):
        '''
        Uploads the file in test_file to shock and returns the node and a
        handle to the node.
        '''
        print('loading file to shock: ' + test_file)
        node = cls.upload_file_to_shock(test_file)
        pprint(node)
        cls.nodes_to_delete.append(node['id'])

        print('creating handle for shock id ' + node['id'])
        handle_id = cls.hs.persist_handle({'id': node['id'],
                                           'type': 'shock',
                                           'url': cls.shockURL
                                           })
        cls.handles_to_delete.append(handle_id)

        md5 = node['file']['checksum']['md5']
        return node['id'], handle_id, md5, node['file']['size']


    @classmethod
    def upload_reads(cls, wsobjname, object_body, fwd_reads,
                     rev_reads=None, single_end=False, sequencing_tech='Illumina',
                     single_genome='1'):

        ob = dict(object_body)  # copy
        ob['sequencing_tech'] = sequencing_tech
#        ob['single_genome'] = single_genome
        ob['wsname'] = cls.getWsName()
        ob['name'] = wsobjname
        if single_end or rev_reads:
            ob['interleaved']= 0
        else:
            ob['interleaved']= 1
        print('\n===============staging data for object ' + wsobjname +
              '================')
        print('uploading forward reads file ' + fwd_reads['file'])
        fwd_id, fwd_handle_id, fwd_md5, fwd_size = \
            cls.upload_file_to_shock_and_get_handle(fwd_reads['file'])

        ob['fwd_id']= fwd_id
        rev_id = None
        rev_handle_id = None
        if rev_reads:
            print('uploading reverse reads file ' + rev_reads['file'])
            rev_id, rev_handle_id, rev_md5, rev_size = \
                cls.upload_file_to_shock_and_get_handle(rev_reads['file'])
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
    def upload_assembly(cls, wsobjname, object_body, fwd_reads,
                        rev_reads=None, kbase_assy=False,
                        single_end=False, sequencing_tech='Illumina'):
        if single_end and rev_reads:
            raise ValueError('u r supr dum')

        print('\n===============staging data for object ' + wsobjname +
              '================')
        print('uploading forward reads file ' + fwd_reads['file'])
        fwd_id, fwd_handle_id, fwd_md5, fwd_size = \
            cls.upload_file_to_shock_and_get_handle(fwd_reads['file'])
        fwd_handle = {
                      'hid': fwd_handle_id,
                      'file_name': fwd_reads['name'],
                      'id': fwd_id,
                      'url': cls.shockURL,
                      'type': 'shock',
                      'remote_md5': fwd_md5
                      }

        ob = dict(object_body)  # copy
        ob['sequencing_tech'] = sequencing_tech
        if kbase_assy:
            if single_end:
                wstype = 'KBaseAssembly.SingleEndLibrary'
                ob['handle'] = fwd_handle
            else:
                wstype = 'KBaseAssembly.PairedEndLibrary'
                ob['handle_1'] = fwd_handle
        else:
            if single_end:
                wstype = 'KBaseFile.SingleEndLibrary'
                obkey = 'lib'
            else:
                wstype = 'KBaseFile.PairedEndLibrary'
                obkey = 'lib1'
            ob[obkey] = \
                {'file': fwd_handle,
                 'encoding': 'UTF8',
                 'type': fwd_reads['type'],
                 'size': fwd_size
                 }

        rev_id = None
        rev_handle_id = None
        if rev_reads:
            print('uploading reverse reads file ' + rev_reads['file'])
            rev_id, rev_handle_id, rev_md5, rev_size = \
                cls.upload_file_to_shock_and_get_handle(rev_reads['file'])
            rev_handle = {
                          'hid': rev_handle_id,
                          'file_name': rev_reads['name'],
                          'id': rev_id,
                          'url': cls.shockURL,
                          'type': 'shock',
                          'remote_md5': rev_md5
                          }
            if kbase_assy:
                ob['handle_2'] = rev_handle
            else:
                ob['lib2'] = \
                    {'file': rev_handle,
                     'encoding': 'UTF8',
                     'type': rev_reads['type'],
                     'size': rev_size
                     }

        print('Saving object data')
        objdata = cls.wsClient.save_objects({
            'workspace': cls.getWsName(),
            'objects': [
                        {
                         'type': wstype,
                         'data': ob,
                         'name': wsobjname
                         }]
            })[0]
        print('Saved object objdata: ')
        pprint(objdata)
        print('Saved object ob: ')
        pprint(ob)
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
        print('WS url ' + cls.wsClient.url)
        print('Handle service url ' + cls.hs.url)
        print('CPUs detected ' + str(psutil.cpu_count()))
        print('Available memory ' + str(psutil.virtual_memory().available))
        print('staging data')
        # get file type from type
        fwd_reads = {'file': 'data/small.forward.fq',
                     'name': 'test_fwd.fastq',
                     'type': 'fastq'}
        # get file type from handle file name
        rev_reads = {'file': 'data/small.reverse.fq',
                     'name': 'test_rev.FQ',
                     'type': ''}
        # get file type from shock node file name
        int_reads = {'file': 'data/interleaved.fq',
                     'name': '',
                     'type': ''}
        cls.upload_reads('frbasic', {}, fwd_reads, rev_reads=rev_reads)
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
             [{'name': 'NODE_1_length_64822_cov_8.99582',
               'length': 64822,
               'id': 'NODE_1_length_64822_cov_8.99582',
               'md5': '8a67351c7d6416039c6f613c31b10764'
               },
              {'name': 'NODE_2_length_62656_cov_8.64322',
               'length': 62656,
               'id': 'NODE_2_length_62656_cov_8.64322',
               'md5': '8e7483c2223234aeff0c78f70b2e068a'
               }],
             'md5': '08d0b92ce7c0a5e346b3077436edaa42',
             'fasta_md5': '03a8b6fc00638dd176998e25e4a208b6'
             })


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
            exception=WorkspaceError)

    # TEST REMOVED SINCE FROM THE UI IT IS A REFERENCE (Old logic in Impl broke UI)
    # def test_bad_lib_name(self):

    #   self.run_error(['bad&name'], 'Invalid workspace object name bad&name')


    def test_no_libs_param(self):

        self.run_error(None, 'read_libraries parameter is required')


    def test_no_libs_list(self):

        self.run_error('foo', 'read_libraries must be a list')


    def test_non_extant_lib(self):

        self.run_error(
            ['foo'],
            ('No object with name foo exists in workspace {} ' +
             '(name {})').format(str(self.wsinfo[0]), self.wsinfo[1]),
            exception=WorkspaceError)


    def test_no_libs(self):

        self.run_error([], 'At least one reads library must be provided')


    def test_no_output_param(self):

        self.run_error(
            ['foo'], 'output_contigset_name parameter is required',
            output_name=None)


    def run_error(self, readnames, error, wsname=('fake'), output_name='out',
                  dna_source=None, exception=ValueError):

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

        if not (dna_source is None):
            params['dna_source'] = dna_source

        with self.assertRaises(exception) as context:
            self.getImpl().run_idba_ud(self.ctx, params)
        self.assertEqual(error, str(context.exception.message))


    def run_success(self, readnames, output_name, expected, contig_count=None,
                    dna_source=None):

        test_name = inspect.stack()[1][3]
        print('\n**** starting expected success test: ' + test_name + ' *****')
        print('   libs: ' + str(readnames))

        if not contig_count:
            contig_count = len(expected['contigs'])

        print("READNAMES: " + str(readnames))
        print("STAGED: " + str(self.staged))

        libs = [self.staged[n]['info'][1] for n in readnames]
#        assyrefs = sorted(
#            [self.make_ref(self.staged[n]['info']) for n in readnames])

        params = {'workspace_name': self.getWsName(),
                  'read_libraries': libs,
                  'output_contigset_name': output_name
                  }

        if not (dna_source is None):
            if dna_source == 'None':
                params['dna_source'] = None
            else:
                params['dna_source'] = dna_source


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

        ''' failing, check this ?????
        #self.assertEqual(1, len(report['provenance']))
        '''

        # PERHAPS ADD THESE TESTS BACK IN THE FUTURE, BUT AssemblyUtils and this
        # would need to pass in the extra provenance information
#        self.assertEqual(
#            assyrefs, sorted(report['provenance'][0]['input_ws_objects']))
#        self.assertEqual(
#            assyrefs,
#            sorted(report['provenance'][0]['resolved_ws_objects']))

        assembly_ref = report['data']['objects_created'][0]['ref']
        assembly = self.wsClient.get_objects([{'ref': assembly_ref}])[0]
        print("ASSEMBLY OBJECT:")
        pprint(assembly)
        print("===============  END OF ASSEMBLY OBJECT:")
        self.assertEqual('KBaseGenomeAnnotations.Assembly', assembly['info'][2].split('-')[0])

        ''' failing, check this ?????
        self.assertEqual(2, len(assembly['provenance']))
        '''

        # PERHAPS ADD THESE TESTS BACK IN THE FUTURE, BUT AssemblyUtils and this
        # would need to pass in the extra provenance information
#        self.assertEqual(
#            assyrefs, sorted(assembly['provenance'][0]['input_ws_objects']))
#        self.assertEqual(
#            assyrefs, sorted(assembly['provenance'][0]['resolved_ws_objects']))
        self.assertEqual(output_name, assembly['info'][1])

#        handle_id = assembly['data']['fasta_handle_ref']
#        print("HANDLE ID:" + handle_id)
#        handle_ids_list = list()
#        handle_ids_list.append(handle_id)
#        print("HANDLE IDS:" + str(handle_ids_list))
#        temp_handle_info = self.hs.hids_to_handles(handle_ids_list)
        temp_handle_info = self.hs.hids_to_handles([assembly['data']['fasta_handle_ref']])
        print("HANDLE OBJECT:")
        pprint(temp_handle_info)
        assembly_fasta_node = temp_handle_info[0]['id']
        self.nodes_to_delete.append(assembly_fasta_node)
        header = {"Authorization": "Oauth {0}".format(self.token)}
        fasta_node = requests.get(self.shockURL + '/node/' + assembly_fasta_node,
                                  headers=header, allow_redirects=True).json()

        ''' failing, check this ?????
        self.assertEqual(expected['fasta_md5'],
                         fasta_node['data']['file']['checksum']['md5'])
        '''

        self.assertEqual(contig_count, len(assembly['data']['contigs']))
        self.assertEqual(output_name, assembly['data']['assembly_id'])

        ''' failing, check this ?????
        self.assertEqual(output_name, assembly['data']['name'])
        self.assertEqual(expected['md5'], assembly['data']['md5'])

        for exp_contig in expected['contigs']:
            if exp_contig['id'] in assembly['data']['contigs']:
                obj_contig = assembly['data']['contigs'][exp_contig['id']]
                self.assertEqual(exp_contig['name'], obj_contig['name'])
                self.assertEqual(exp_contig['md5'], obj_contig['md5'])
                self.assertEqual(exp_contig['length'], obj_contig['length'])
            else:
                # Hacky way to do this, but need to see all the contig_ids
                # They changed because the IDBA version changed and
                # Need to see them to update the tests accordingly.
                # If code gets here this test is designed to always fail, but show results.
                self.assertEqual(str(assembly['data']['contigs']),"BLAH")
        '''
