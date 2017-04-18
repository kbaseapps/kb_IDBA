/*
A KBase module: kb_IDBA
A simple wrapper for IDBA-UD Assembler
https://github.com/loneknightpy/idba - Version 1.1.3

????
Always runs in careful mode.
Runs 3 threads / CPU.
Maximum memory use is set to available memory - 1G.
Autodetection is used for the PHRED quality offset and k-mer sizes.
A coverage cutoff is not specified.

*/

module kb_IDBA {

    /* A boolean. 0 = false, anything else = true. */
    typedef int bool;
    
    /* The workspace object name of a PairedEndLibrary file, whether of the
       KBaseAssembly or KBaseFile type.
    */
    typedef string paired_end_lib;
    
    /* Input parameters for running IDBA.
        string workspace_name - the name of the workspace from which to take
           input and store output.
        string output_contigset_name - the name of the output contigset
        list<paired_end_lib> read_libraries - Illumina PairedEndLibrary files
            to assemble.
        string dna_source - the source of the DNA used for sequencing
            'single_cell': DNA amplified from a single cell via MDA
            anything else: Standard DNA sample from multiple cells
        
    */
    typedef structure {
        string workspace_name;
        string output_contigset_name;
        list<paired_end_lib> read_libraries;
        string dna_source;
	int min_contig_len;
    } IDBA_Params;
    
    /* Output parameters for IDBA run.
        string report_name - the name of the KBaseReport.Report workspace
            object.
        string report_ref - the workspace reference of the report.
    */
    typedef structure {
        string report_name;
        string report_ref;
    } IDBA_Output;
    
    /* Run IDBA on paired end libraries */
    funcdef run_IDBA(IDBA_Params params) returns(IDBA_Output output)
        authentication required;
};
