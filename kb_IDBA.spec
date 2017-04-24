/*
A KBase module: kb_IDBA
A simple wrapper for IDBA-UD Assembler
https://github.com/loneknightpy/idba - Version 1.1.3
*/

module kb_IDBA {

    /* The workspace object name of a PairedEndLibrary file, whether of the
       KBaseAssembly or KBaseFile type.
    */
    typedef string paired_end_lib;

    /* Input parameters for running idba_ud.
        string workspace_name - the name of the workspace from which to take
           input and store output.
        list<paired_end_lib> read_libraries - Illumina PairedEndLibrary files
            to assemble.
        string output_contigset_name - the name of the output contigset
    */
    typedef structure {
        string workspace_name;
        list<paired_end_lib> read_libraries;  /*  input reads  */
        string output_contigset_name;         /*  name of output contigs */
        int mink_arg;                  /*  (=20)  minimum k value (<=124) */
        int maxk_arg;                  /*  (=50)  maximum k value (<=124) */
        int step_arg;                  /*  (=10)  increment of k-mer of each iteration  */
        int min_contig_arg;            /*  (=200) minimum size of contig */
    } idba_ud_Params;
    
    /* Output parameters for IDBA run.
        string report_name - the name of the KBaseReport.Report workspace
            object.
        string report_ref - the workspace reference of the report.
    */
    typedef structure {
        string report_name;
        string report_ref;
    } idba_ud_Output;
    
    /* Run IDBA on paired end libraries */
    funcdef run_idba_ud(idba_ud_Params params) returns(idba_ud_Output output)
        authentication required;
};
