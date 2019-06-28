### Version 1.0.4
__Changes__
- updated docs

### Version 1.0.3
__Changes__
- updated base image to sdkbase2

### Version 1.0.2
__Changes__
- changed citation to PLOS format 

### Version 1.0.1
__Changes__
- changed contact from email to url

### Version 1.0.0
__Changes__
- updated min_contig_arg to min_contig_length (to be consistent with other MG assembler arg names) and set default to 2Kbp and min of 300bp (also to be consistent).

### Version 0.0.1
__Initial version of the wrapper for IDBA-UD assembler__
- IDBA is in https://github.com/loneknightpy/idba. Version 1.1.3
- This module uses fq2fa to convert the input paired end library from fastq to fasta format
- The fasta file is given as input to idba_ud as described in the above page
- The assembler is recompiled to support longer reads upto 512bp
