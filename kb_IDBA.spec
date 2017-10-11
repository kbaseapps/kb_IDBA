/*
A KBase module: kb_IDBA
A simple wrapper for IDBA-UD Assembler
https://github.com/loneknightpy/idba - Version 1.1.3
*/

module kb_IDBA {

    /*
        The workspace object name of a PairedEndLibrary file, whether of the
        KBaseAssembly or KBaseFile type.
    */

    typedef string paired_end_lib;

    /*
        Additional parameters: k values for idba_ud.
        (Note: The UI elements for these values have been removed, based on feedback)
    */

    typedef structure {
        int mink_arg;      /*  minimum k value (<=124) (Default: 20)   */
        int maxk_arg;      /*  maximum k value (<=124) (Default: 100)  */
        int step_arg;      /*  increment of k-mer of each iteration (Default: 20)  */
    } kval_args_type;


    /*
       Input parameters for running idba_ud.

        string workspace_name - the name of the workspace from which to take input and store output.
        list<paired_end_lib> read_libraries - Illumina PairedEndLibrary files to assemble.
        string output_contigset_name - the name of the output contigset
        min_contig_length - minimum length of contigs to output, default is 2000

        @optional kval_args
    */

    typedef structure {
        string               workspace_name;
        list<paired_end_lib> read_libraries;          /*  input reads  */
        string               output_contigset_name;   /*  name of output contigs */
        int                  min_contig_length;          /*  minimum size of contig (default: 2000) */
        kval_args_type       kval_args;               /*  additional parameters */
    } idba_ud_Params;


    /*
       Output parameters for IDBA run.

        string report_name - the name of the KBaseReport.Report workspace object.
        string report_ref  - the workspace reference of the report.
    */

    typedef structure {
        string report_name;
        string report_ref;
    } idba_ud_Output;
    
    /* Run IDBA on paired end libraries */

    funcdef run_idba_ud(idba_ud_Params params) returns(idba_ud_Output output)
        authentication required;
};
