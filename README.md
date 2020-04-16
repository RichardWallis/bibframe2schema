# bibframe2schema
Working files for the Bibframe2Schema.org Working Group <https://www.w3.org/community/bibframe2schema>


## **Component Files**

**scripts**
This area contains scripts for processing source Bibframe data to obtain Schema.org data.

* ***schemaise.py***
  This is an open source general purpose python script for processing RDF data, which has been tweaked a little to make it particularly useful to Bibframe2Schema.org.
  
  Its operation is controlled by passing command-line parameters:
  
  * *--input* *-i* Source input RDF file, or URL of input RDF file, or directory containing one or more RDF files. Acceptable formats (RDF/XML, json-ld, turtle, nt).
  * *--output* *-o* Output file (for single file) or directory for multiple files. 
  * *--outfile* *-O* Overriding output file name
  * *--batchload* *-b* Load all input files then output combination into single output file
  * *--format* *-f* Serialisation format fot output files (xml|rdf|n3|turtle|nt|nquads|jsonld) - influences output file name extension. Default format turtle.
  * *--query* *-q* File, or directory of files, containing SPARQL query scripts to process imported RDF data to produce output RDF data.
  * *--tokenfile* *-t* File (in JSON) format containing name-value variable pairs for substitution in loaded SPARQL query scripts before being used for processing.
  * *--querycount* *-c* Number of times to process query scripts before outputting resultant data. Default count 1.
  * *--schemaonly* *-s* Only output triples that contain a URI from the Schema.org vocabulary as a subject or predicate.
  * *--preprocess* *-p* Source preprocess function (eg. LoCSRUResponse).  Function to process input data before attempting to load RDF from it
  * *-v* Run in verbose mode.
  * *--version* *-V* Output version
  
  Principle of opperation:
  * Load each source file, or URL, in turn into an auto-generated RDF triple-store.  RDF syntax used is auto scensed - see rdflib documentation for details.
  * Load each query script and substitute tokens in source with configured tokens:
  * * Replace [[TODAY]], [[NOW]] with default values.
  * * Replace tokens of the form [[TOKENNAME]] with value as defined in token file in the form ```"TOKENNAME": "Tokn value"```.
  * Process each query, in sorted order, against each triple-store. 
  * Repeat *querycount* times
  * If *schemaonly* is selected, all triples except those containing URIs from Schema.org vocabulary are deleted from triple-store
  * Contents of triple-store are serialised in the chosen format to output file, or a file (name calculated from the input filename and the output format)
  * In batchload mode, all source files are loaded before processing is commenced.  This results in a single combined output file.
  
  
  Example operation from source directory:
   
   ```scripts/schemaise.py -i tests/source -o tests/out -q query/bibframe2schema.sparql -t tokens.json -f jsonld -s -v```
  
  Example operation  for individual source file:
   
   ```scripts/schemaise.py -i tests/source/LCCN-98033893.xml -o tests/out -q query/bibframe2schema.sparql -t tokens.json -f jsonld -s -v```
  
  Example operation  for individual URL file:
    
    ```scripts/schemaise.py -i https://raw.githubusercontent.com/RichardWallis/bibframe2schema/master/tests/source/LCCN-98033893.xml -o tests/out -q query/bibframe2schema.sparql -t tokens.json -f jsonld -s -v```

### Operational Environment and Dependancies:
  
  *schemaise.py* Is a python script tested with Python versions 2.7 & 3.6 on Linux-like operating systems (incuding Mac-OS).  It depends on some python libraries
  that may need loading, using the ```pip install``` command.  These include ```json```, ```rdflib```, ```rdflib_jsonld```.
  
**query**

This area contains SPARQL scripts for processing source Bibframe data to obtain Schema.org data.

* ***bibframe2schema.sparql***

  SPARQL Script, using the INSERT verb, to add Schema.org triples to existing Bibframe (2.0) description.

Intended for use as an input query script for the *schemaise.py* script.  It makes use of the token substitution syntax to insert the processing date, structured data licensing and publisher into resultant triples.

**tokens.json**

File containing token name-value pairs for substitution in a SPARQL query script being processed by the *schemaise.py* script.  See [tokens.md](tokens.md) for details.


**tests**

Area for running test conversions.  Includes example source file(s) and resultant output files.

### Source Preprocessing:
 
 **LoCSRUResponse**

Preprocessor (instigated using ```-p LoCSRUResponse```) designed to handle XML output from Library of Congress search request which captures RDF output within a ```searchRetrieveResponse``` element structure. 





