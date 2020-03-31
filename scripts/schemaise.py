#!/usr/bin/env python
###################################################################
# 
# schemaise.py
# Version: 0.9
#
# Script for processing RDF data, which has been tweaked a little to make it particularly useful to Bibframe2Schema.org.
#  
#  Its operation is controlled by passing command-line parameters:
# 
#   --input Source input RDF file, or directory containing one or more RDF files. Acceptable formats (RDF/XML, json-ld, turtle, nt).
#   --output Output file (for single file) or directory for multiple files.  
#   --format Serialisation format fot output files (xml|rdf|n3|turtle|nt|nquads|jsonld) - influences output file name extension. Default format turtle.
#   --query File, or directory of files, containing SPARQL query scripts to process imported RDF data to produce output RDF data.
#   --tokenfile File (in JSON) format containing name-value variable pairs for substitution in loaded SPARQL query scripts before being used for processing.
#   --querycount Number of times to process query scripts before outputting resultant data. Default count 1.
#   --schemaonly Only ouput triples that contain a URI from the Schema.org vocabulary as a subject or predicate.
#   -v Run in verbose mode.
#
# Copyright (c) 2020 Richard Wallis - Data Liberate <https://dataliberate.com>
# Originator Richard Wallis
# Licenced under Creative Commons Licence CC0 <https://creativecommons.org/publicdomain/zero/1.0>
#
###################################################################

import sys
import os
import re
import datetime
import argparse
import urllib
import rdflib 
import logging 
logging.basicConfig(level=logging.CRITICAL) 
log = logging.getLogger(__name__)


from rdflib.parser import Parser
from rdflib.serializer import Serializer

rdflib.plugin.register("jsonld", Parser, "rdflib_jsonld.parser", "JsonLDParser")
rdflib.plugin.register("jsonld", Serializer, "rdflib_jsonld.serializer", "JsonLDSerializer")

EXTS = {"xml": ".xml",
        "rdf": ".rdf",
        "turtle": ".ttl",
        "nt": "nt",
        "nquads": ".nq",
        "jsonld": ".jsonld"}

BATCH = True
SOURCE="."
OUT='-'
QUERIES=[]
TOKENS=None
TOKENFILE=None
VERBOSE=False
SCHEMASTRIP=False
FORMAT = "turtle"

SCHEMAONLY="""
prefix schema: <http://schema.org/> 
DELETE {
    ?s ?p ?o.
} WHERE {
    ?s ?p ?o.
    FILTER ( ! (strstarts(str(?p),"http://schema.org") || strstarts(str(?o),"http://schema.org")) )
}"""

def getOut(file=""):
    global OUT, BATCH, SOURCE, QUERIES, FORMAT
    if OUT == '-':
        return sys.stdout
    elif os.path.isdir(OUT):
        if not BATCH:
            file = "%s/%s" % (OUT,file[len(SOURCE)+1:])
        else:
            file = "%s/output" % OUT
    else:
        file = OUT
        
    froot = os.path.splitext(file)[0]
    file = froot + EXTS[FORMAT]
        
    report("Output file: %s" %file)
    if not os.path.exists(os.path.dirname(file)):
        report("Creating directory path for file")
        os.makedirs(os.path.dirname(file))
    return open(file,"w")

def runQueryFile(graph=None,query=None):
    if not graph or not query:
        return
    with open(query, 'r') as myfile:
      runQuery(graph,myfile.read())

def runQuery(graph=None,queryText=None):
    if not graph or not queryText:
        return
    text = tokenSubstitute(queryText)
    
    if re.search('INSERT', text, re.IGNORECASE) or re.search('DELETE', text, re.IGNORECASE):
        graph.update(text)
    else:
        graph.query(text)
        
def tokenSubstitute(string):
    import json
    global TOKENFILE,TOKENS
    
    if not TOKENS:
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        TOKENS = {
            "TODAY": today,
            "NOW": now
        }
        
        if TOKENFILE:
            with open(TOKENFILE) as json_file:
                data = json.load(json_file)
                TOKENS.update(data)

    if TOKENS:
        for t, v in TOKENS.items():
            string = string.replace("[[%s]]" % t ,v)
    #report(string)
    return string
    

        
def report(msg):
    global VERBOSE
    if not VERBOSE:
        return
    print(msg)
                  
    
def main():
    global OUT, BATCH, SOURCE, QUERIES, VERBOSE, FORMAT, TOKENFILE
    infiles = []
    query = None
    parser = argparse.ArgumentParser()
    parser.add_argument("-i","--input", required=True, help="Input rdf file | input dir")
    parser.add_argument("-o","--output", required=True, help="Output file | - (stdout) | output dir")
    parser.add_argument("-f","--format",default="turtle", help="Output format (xml|rdf|n3|turtle|nt|nquads|jsonld)")
    parser.add_argument("-q","--query", help="Source sparql query files | queries dir")
    parser.add_argument("-t","--tokenfile", help="File containing substitute token mappings")
    parser.add_argument("-c","--querycount", type=int, default=1, help="Number of times to itterate through queries")
    parser.add_argument("-s","--schemaonly", action='store_true', help="Only output Schema.org triples")
    parser.add_argument("-v", action='store_true', help="Verbose output")
    args = parser.parse_args()
    
    VERBOSE = args.v
    SCHEMASTRIP=args.schemaonly
    TOKENFILE=args.tokenfile
    queryCount = args.querycount
    
    
    if os.path.isdir(args.input):
        SOURCE=args.input
        for (dirpath, dirnames, filenames) in os.walk(SOURCE):
            for f in filenames:
                if not f.startswith('.'):
                    infiles.append(dirpath+"/"+f)
    else:
        infiles = [args.input]
        
    report("Files to process: %s" % len(infiles))
    
    if len(infiles) == 1:
        BATCH = False
    
        
    OUT = args.output
    
    if BATCH:
        if not os.path.exists(OUT):
            os.makedirs(OUT)
            
    if os.path.isdir(OUT):
        BATCH=False
        
    report("BATCH Mode: %s" % BATCH)
        
    
    if args.format:
        FORMAT = args.format
        outf = FORMAT
        if FORMAT == "xml" or FORMAT == "rdf":
            outf = "pretty-xml"

    if FORMAT not in EXTS:
        print("Unsupported format: %s" % FORMAT)
        sys.exit()

    if args.query and os.path.isdir(args.query):
        for (dirpath, dirnames, filenames) in os.walk(args.query):
            for f in filenames:
                if not f.startswith('.'):
                    QUERIES.append(dirpath+"/"+f)
            break #Don't go into sub directories        
    else:
        QUERIES = [args.query]
        
        
    
    if BATCH: #Load all file before process
        g = rdflib.Graph()
        g.bind('schema', 'http://schema.org/')
        for f in infiles:
            if not os.path.exists(f):
                report("No such file: %s" % f)
                continue
            try:
                g.parse(f)
                report("Loaded : %s" % f)
            except:
                pass
            g.bind('schema', 'http://schema.org/')
            
        count=0
        while count < queryCount:
            count+=1
            if queryCount > 1:
                report("Queries pass No: %s" % (count))
            for q in sorted(QUERIES):
                report("Running query: %s" % q)
                runQueryFile(graph=g,query=q)
            
    else: #Single mode
        for f in infiles:
            if not os.path.exists(f):
                report("No such file: %s" % f)
                continue
            g = rdflib.Graph()
            try:
                g.parse(f)
                report("Loaded: %s" % f)
            except:
                pass
            g.bind('schema', 'http://schema.org/')
            count=0
            while count < queryCount:
                count+=1
                if queryCount > 1:
                    report("Queries pass No: %s" % (count))
                for q in sorted(QUERIES):
                    report("Running query: %s" % q)
                    runQueryFile(graph=g,query=q)
                
        if SCHEMASTRIP:
            report("Stripping none Schema.org triples")
            runQuery(graph=g,queryText=SCHEMAONLY)
        out = getOut(file=f)
        out.write(g.serialize(format = outf,auto_compact=True).decode('utf-8'))
        out.close()
    

if __name__ == "__main__":
    main()