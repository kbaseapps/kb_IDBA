# -*- coding: utf-8 -*-
#BEGIN_HEADER
# The header block is where all import statements should live
from __future__ import print_function
import os
import re
import uuid
from pprint import pformat
from pprint import pprint
from biokbase.workspace.client import Workspace as workspaceService
import subprocess
import numpy as np
from ReadsUtils.ReadsUtilsClient import ReadsUtils
from ReadsUtils.baseclient import ServerError
from AssemblyUtil.AssemblyUtilClient import AssemblyUtil
from KBaseReport.KBaseReportClient import KBaseReport
from kb_quast.kb_quastClient import kb_quast
import time
from datetime import datetime
import psutil

class ShockException(Exception):
    pass

#END_HEADER


class kb_IDBA:
    '''
    Module Name:
    kb_IDBA

    Module Description:
    A KBase module: kb_IDBA
A simple wrapper for IDBA-UD Assembler
https://github.com/loneknightpy/idba - Version 1.1.3
    '''

    ######## WARNING FOR GEVENT USERS ####### noqa
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    ######################################### noqa
    VERSION = "1.0.3"
    GIT_URL = "https://github.com/kbaseapps/kb_IDBA"
    GIT_COMMIT_HASH = "6e9c10dc082d1223abd18b3b4ac8771c43704695"

    #BEGIN_CLASS_HEADER
    # Class variables and functions can be defined in this block
    DISABLE_FQ2FA_OUTPUT = False  # should be False in production
    DISABLE_IDBA_OUTPUT = False  # should be False in production

    PARAM_IN_WS = 'workspace_name'
    PARAM_IN_LIB = 'read_libraries'
    PARAM_IN_CS_NAME = 'output_contigset_name'
    PARAM_IN_MIN_CONTIG = 'min_contig_length'
    PARAM_IN_KVAL_ARGS = 'kval_args'
    PARAM_IN_MIN_K_ARG = 'mink_arg'
    PARAM_IN_MAX_K_ARG = 'maxk_arg'
    PARAM_IN_STEP_ARG = 'step_arg'

    INVALID_WS_OBJ_NAME_RE = re.compile('[^\\w\\|._-]')
    INVALID_WS_NAME_RE = re.compile('[^\\w:._-]')

    THREADS_PER_CORE = 1

    URL_WS = 'workspace-url'
    URL_SHOCK = 'shock-url'
    URL_KB_END = 'kbase-endpoint'

    TRUE = 'true'
    FALSE = 'false'

    # code taken from kb_SPAdes

    def log(self, message, prefix_newline=False):
        print(('\n' if prefix_newline else '') +
              str(time.time()) + ': ' + str(message))


    def exec_fq2fa(self, input_reads, outdir):

        if not os.path.exists(outdir):
            os.makedirs(outdir)

        outfile_fasta = os.path.join(outdir, 'fq2fa-output.fasta')

        # fq2fa command part of IDBA package
        fq2fa_cmd = ['fq2fa', '--merge', '--filter',
                      input_reads['fwd_file'],  input_reads['rev_file'],
                      outfile_fasta]

        print("fq2fa CMD:" + str(fq2fa_cmd))
        self.log(fq2fa_cmd)

        if self.DISABLE_FQ2FA_OUTPUT:
            with open(os.devnull, 'w') as null:
                p = subprocess.Popen(fq2fa_cmd, cwd=self.scratch, shell=False,
                                     stdout=null)
        else:
            p = subprocess.Popen(fq2fa_cmd, cwd=self.scratch, shell=False)

        retcode = p.wait()

        self.log('Return code: ' + str(retcode))
        if p.returncode != 0:
            raise ValueError('Error running fq2fa, return code: ' +
                             str(retcode) + '\n')
        return outfile_fasta


    def exec_idba_ud(self, reads_data, params_in, outdir):

        threads = psutil.cpu_count() * self.THREADS_PER_CORE

        if not os.path.exists(outdir):
            os.makedirs(outdir)

        # The fq2fa can only be run on a single library
        # The library must be paired end.
        if len(reads_data) > 1 or reads_data[0]['type'] != 'paired':
            error_msg = 'IDBA-UD assembly requires that one and ' + \
                            'only one paired end library as input.'
            if len(reads_data) > 1:
                error_msg += ' ' + str(len(reads_data)) + \
                                 ' libraries detected.'
            raise ValueError(error_msg)

        print("LENGTH OF READSDATA IN EXEC: " + str(len(reads_data)))

        # first convert input reads_data from fastq to fasta
        # output fasta file saved in fq2fa_outfile

        fq2fa_outfile = self.exec_fq2fa(reads_data[0], outdir)

        outdir_idba = os.path.join(outdir, 'IDBA_output')

        # use fq2fa_outfile as input to idba_ud assembler
        # output files from the assembler saved in outdir

        idba_ud_cmd = ['idba_ud', '-r', fq2fa_outfile,
                       '--num_threads', str(threads),
                       '-o', outdir_idba]

        if self.PARAM_IN_MIN_CONTIG in params_in and int(params_in[self.PARAM_IN_MIN_CONTIG]) >= 0:
            idba_ud_cmd.append('--min_contig')
            idba_ud_cmd.append(str(params_in[self.PARAM_IN_MIN_CONTIG]))

        if self.PARAM_IN_KVAL_ARGS in params_in and params_in[self.PARAM_IN_KVAL_ARGS] is not None:
            kargs = params_in[self.PARAM_IN_KVAL_ARGS]
            if int(kargs[self.PARAM_IN_MIN_K_ARG]) >= 1:
                idba_ud_cmd.append('--mink')
                idba_ud_cmd.append(str(kargs[self.PARAM_IN_MIN_K_ARG]))

            if int(kargs[self.PARAM_IN_MAX_K_ARG]) >= 2:
                idba_ud_cmd.append('--maxk')
                idba_ud_cmd.append(str(kargs[self.PARAM_IN_MAX_K_ARG]))

            if int(kargs[self.PARAM_IN_STEP_ARG]) > 0:
                idba_ud_cmd.append('--step')
                idba_ud_cmd.append(str(kargs[self.PARAM_IN_STEP_ARG]))

        print("\nidba_ud CMD:     " + str(idba_ud_cmd))
        self.log(idba_ud_cmd)

        if self.DISABLE_IDBA_OUTPUT:
            with open(os.devnull, 'w') as null:
                p = subprocess.Popen(idba_ud_cmd, cwd=self.scratch, shell=False,
                                     stdout=null)
        else:
            p = subprocess.Popen(idba_ud_cmd, cwd=self.scratch, shell=False)

        retcode = p.wait()

        self.log('Return code: ' + str(retcode))
        if p.returncode != 0:
            raise ValueError('Error running IDBA, return code: ' +
                             str(retcode) + '\n')

        return outdir_idba


    # adapted from
    # https://github.com/kbase/transform/blob/master/plugins/scripts/convert/
    # trns_transform_KBaseFile_AssemblyFile_to_KBaseGenomes_ContigSet.py
    # which was adapted from an early version of
    # https://github.com/kbase/transform/blob/master/plugins/scripts/upload/
    # trns_transform_FASTA_DNA_Assembly_to_KBaseGenomes_ContigSet.py

    def load_stats(self, input_file_name):
        self.log('Starting conversion of FASTA to KBaseGenomeAnnotations.Assembly')
        self.log('Building Object.')
        if not os.path.isfile(input_file_name):
            raise Exception('The input file name {0} is not a file!'.format(
                input_file_name))
        with open(input_file_name, 'r') as input_file_handle:
            contig_id = None
            sequence_len = 0
            fasta_dict = dict()
            first_header_found = False
            # Pattern for replacing white space
            pattern = re.compile(r'\s+')
            for current_line in input_file_handle:
                if (current_line[0] == '>'):
                    # found a header line
                    # Wrap up previous fasta sequence
                    if not first_header_found:
                        first_header_found = True
                    else:
                        fasta_dict[contig_id] = sequence_len
                        sequence_len = 0
                    fasta_header = current_line.replace('>', '').strip()
                    try:
                        contig_id = fasta_header.strip().split(' ', 1)[0]
                    except:
                        contig_id = fasta_header.strip()
                else:
                    sequence_len += len(re.sub(pattern, '', current_line))
        # wrap up last fasta sequence, should really make this a method
        if not first_header_found:
            raise Exception("There are no contigs in this file")
        else:
            fasta_dict[contig_id] = sequence_len
        return fasta_dict


    def load_report(self, input_file_name, params, wsname):
        fasta_stats = self.load_stats(input_file_name)
        lengths = [fasta_stats[contig_id] for contig_id in fasta_stats]

        assembly_ref = params[self.PARAM_IN_WS] + '/' + params[self.PARAM_IN_CS_NAME]

        report = ''
        report += 'Assembly saved to: ' + assembly_ref + '\n'
        report += 'Assembled into ' + str(len(lengths)) + ' contigs.\n'
        report += 'Avg Length: ' + str(sum(lengths) / float(len(lengths))) + \
            ' bp.\n'

        # compute a simple contig length distribution
        bins = 10
        counts, edges = np.histogram(lengths, bins)  # @UndefinedVariable
        report += 'Contig Length Distribution (# of contigs -- min to max ' +\
            'basepairs):\n'
        for c in range(bins):
            report += '   ' + str(counts[c]) + '\t--\t' + str(edges[c]) +\
                ' to ' + str(edges[c + 1]) + ' bp\n'
        print('Running QUAST')
        kbq = kb_quast(self.callbackURL)
        quastret = kbq.run_QUAST({'files': [{'path': input_file_name,
                                             'label': params[self.PARAM_IN_CS_NAME]}]})
        print('Saving report')
        kbr = KBaseReport(self.callbackURL)
        report_info = kbr.create_extended_report(
            {'message': report,
             'objects_created': [{'ref': assembly_ref, 'description': 'Assembled contigs'}],
             'direct_html_link_index': 0,
             'html_links': [{'shock_id': quastret['shock_id'],
                             'name': 'report.html',
                             'label': 'QUAST report'}
                            ],
             'report_object_name': 'kb_IDBA-UD_report_' + str(uuid.uuid4()),
             'workspace_name': params['workspace_name']
            })
        reportName = report_info['name']
        reportRef = report_info['ref']
        return reportName, reportRef


    def make_ref(self, object_info):
        return str(object_info[6]) + '/' + str(object_info[0]) + \
            '/' + str(object_info[4])


    def check_reads(self, reads, reftoname):

        for ref in reads:
            rds = reads[ref]
            obj_name = reftoname[ref]
            obj_ref = rds['ref']

            if rds['read_orientation_outward'] == self.TRUE:
                raise ValueError(
                    ('Reads object {} ({}) is marked as having outward ' +
                     'oriented reads, which IDBA-UD does not ' +
                     'support.').format(obj_name, obj_ref))


    def process_params(self, params):
        if (self.PARAM_IN_WS not in params or
                not params[self.PARAM_IN_WS]):
            raise ValueError(self.PARAM_IN_WS + ' parameter is required')
        if self.INVALID_WS_NAME_RE.search(params[self.PARAM_IN_WS]):
            raise ValueError('Invalid workspace name ' +
                             params[self.PARAM_IN_WS])
        if self.PARAM_IN_LIB not in params:
            raise ValueError(self.PARAM_IN_LIB + ' parameter is required')
        if type(params[self.PARAM_IN_LIB]) != list:
            raise ValueError(self.PARAM_IN_LIB + ' must be a list')
        if not params[self.PARAM_IN_LIB]:
            raise ValueError('At least one reads library must be provided')
        if (self.PARAM_IN_CS_NAME not in params or
                not params[self.PARAM_IN_CS_NAME]):
            raise ValueError(self.PARAM_IN_CS_NAME + ' parameter is required')
        if self.INVALID_WS_OBJ_NAME_RE.search(params[self.PARAM_IN_CS_NAME]):
            raise ValueError('Invalid workspace object name ' +
                             params[self.PARAM_IN_CS_NAME])

        if self.PARAM_IN_MIN_CONTIG in params:
            if not isinstance(params[self.PARAM_IN_MIN_CONTIG], int):
                raise ValueError('min_contig must be of type int')

        if self.PARAM_IN_KVAL_ARGS in params and params[self.PARAM_IN_KVAL_ARGS] is not None:
            oargs = params[self.PARAM_IN_KVAL_ARGS]
            if not isinstance(oargs[self.PARAM_IN_MIN_K_ARG], int):
                raise ValueError('min k value must be of type int')
            if not isinstance(oargs[self.PARAM_IN_MAX_K_ARG], int):
                raise ValueError('max k value must be of type int')
            if not isinstance(oargs[self.PARAM_IN_STEP_ARG], int):
                raise ValueError('step value must be of type int')

    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.callbackURL = os.environ['SDK_CALLBACK_URL']
        self.log('Callback URL: ' + self.callbackURL)
        self.workspaceURL = config[self.URL_WS]
        self.shockURL = config[self.URL_SHOCK]
        self.catalogURL = config[self.URL_KB_END] + '/catalog'
        self.scratch = os.path.abspath(config['scratch'])
        if not os.path.exists(self.scratch):
            os.makedirs(self.scratch)
        #END_CONSTRUCTOR
        pass


    def run_idba_ud(self, ctx, params):
        """
        Run IDBA on paired end libraries
        :param params: instance of type "idba_ud_Params" (Input parameters
           for running idba_ud. string workspace_name - the name of the
           workspace from which to take input and store output.
           list<paired_end_lib> read_libraries - Illumina PairedEndLibrary
           files to assemble. string output_contigset_name - the name of the
           output contigset min_contig_length - minimum length of contigs to
           output, default is 2000 @optional kval_args) -> structure:
           parameter "workspace_name" of String, parameter "read_libraries"
           of list of type "paired_end_lib" (The workspace object name of a
           PairedEndLibrary file, whether of the KBaseAssembly or KBaseFile
           type.), parameter "output_contigset_name" of String, parameter
           "min_contig_length" of Long, parameter "kval_args" of type
           "kval_args_type" (Additional parameters: k values for idba_ud.
           (Note: The UI elements for these values have been removed, based
           on feedback)) -> structure: parameter "mink_arg" of Long,
           parameter "maxk_arg" of Long, parameter "step_arg" of Long
        :returns: instance of type "idba_ud_Output" (Output parameters for
           IDBA run. string report_name - the name of the KBaseReport.Report
           workspace object. string report_ref  - the workspace reference of
           the report.) -> structure: parameter "report_name" of String,
           parameter "report_ref" of String
        """
        # ctx is the context object
        # return variables are: output
        #BEGIN run_idba_ud
        
        print("===================  IN run_idba_ud")

        print("PARAMS: ")
        pprint(params)
        print("============================   END OF PARAMS: ")

        # A whole lot of this is adapted or outright copied from
        # https://github.com/msneddon/MEGAHIT
        self.log('Running run_idba_ud with params:\n' + pformat(params))

        token = ctx['token']

        # the reads should really be specified as a list of absolute ws refs
        # but the narrative doesn't do that yet
        self.process_params(params)

        # get absolute refs from ws
        wsname = params[self.PARAM_IN_WS]
        obj_ids = []
        for r in params[self.PARAM_IN_LIB]:
            obj_ids.append({'ref': r if '/' in r else (wsname + '/' + r)})
        ws = workspaceService(self.workspaceURL, token=token)
        ws_info = ws.get_object_info_new({'objects': obj_ids})
        reads_params = []

        reftoname = {}
        for wsi, oid in zip(ws_info, obj_ids):
            ref = oid['ref']
            reads_params.append(ref)
            obj_name = wsi[1]
            reftoname[ref] = wsi[7] + '/' + obj_name

        readcli = ReadsUtils(self.callbackURL, token=ctx['token'])

        typeerr = ('Supported types: KBaseFile.SingleEndLibrary ' +
                   'KBaseFile.PairedEndLibrary ' +
                   'KBaseAssembly.SingleEndLibrary ' +
                   'KBaseAssembly.PairedEndLibrary')
        try:
            reads = readcli.download_reads({'read_libraries': reads_params,
                                            'interleaved': 'false',
                                            'gzipped': None
                                            })['files']
        except ServerError as se:
            self.log('logging stacktrace from dynamic client error')
            self.log(se.data)
            if typeerr in se.message:
                prefix = se.message.split('.')[0]
                raise ValueError(
                    prefix + '. Only the types ' +
                    'KBaseAssembly.PairedEndLibrary ' +
                    'and KBaseFile.PairedEndLibrary are supported')
            else:
                raise

        self.log('Got reads data from converter:\n' + pformat(reads))

        self.check_reads(reads, reftoname)

        reads_data = []
        for ref in reads:
            reads_name = reftoname[ref]
            f = reads[ref]['files']
            print ("REF:" + str(ref))
            print ("READS REF:" + str(reads[ref]))
            seq_tech = reads[ref]["sequencing_tech"]
            if f['type'] == 'interleaved':
                reads_data.append({'fwd_file': f['fwd'], 'type':'paired',
                                   'seq_tech': seq_tech})
            elif f['type'] == 'paired':
                reads_data.append({'fwd_file': f['fwd'], 'rev_file': f['rev'],
                                   'type':'paired', 'seq_tech': seq_tech})
            elif f['type'] == 'single':
                reads_data.append({'fwd_file': f['fwd'], 'type':'single',
                                   'seq_tech': seq_tech})
            else:
                raise ValueError('Something is very wrong with read lib' + reads_name)

        # set the output location
        timestamp = int((datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds() * 1000)
        outdir = os.path.join(self.scratch, 'IDBA_dir' + str(timestamp))

        idba_out = self.exec_idba_ud(reads_data, params, outdir)
        self.log('IDBA output dir: ' + idba_out)

        # parse the output and save back to KBase
        output_contigs = os.path.join(idba_out, 'contig.fa')

        self.log('Uploading FASTA file to Assembly')
        assemblyUtil = AssemblyUtil(self.callbackURL, token=ctx['token'], service_ver='dev')
        if params.get('min_contig_length', 0) > 0:
            assemblyUtil.save_assembly_from_fasta({'file': {'path': output_contigs},
                                                   'workspace_name': wsname,
                                                   'assembly_name': params[self.PARAM_IN_CS_NAME],
                                                   'min_contig_length': params['min_contig_length']
                                               })
            # load report from scaffolds.fasta
            report_name, report_ref = self.load_report(output_contigs+'.filtered.fa', params, wsname)
        else:
            assemblyUtil.save_assembly_from_fasta({'file': {'path': output_contigs},
                                                   'workspace_name': wsname,
                                                   'assembly_name': params[self.PARAM_IN_CS_NAME]
                                               })
            # load report from scaffolds.fasta
            report_name, report_ref = self.load_report(output_contigs, params, wsname)

        output = {'report_name': report_name,
                  'report_ref': report_ref
                  }

        #END run_idba_ud

        # At some point might do deeper type checking...
        if not isinstance(output, dict):
            raise ValueError('Method run_idba_ud return value ' +
                             'output is not type dict as required.')
        # return the results
        return [output]
    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {'state': "OK",
                     'message': "",
                     'version': self.VERSION,
                     'git_url': self.GIT_URL,
                     'git_commit_hash': self.GIT_COMMIT_HASH}
        del ctx  # shut up pep8
        #END_STATUS
        return [returnVal]
