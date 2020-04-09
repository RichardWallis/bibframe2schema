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
VER="1.01"
import sys
import os
import re
import datetime
import argparse
import urllib
import rdflib
import json
 

if sys.version_info.major == 2:
    from urlparse import urlparse
elif sys.version_info.major == 3:
    from urllib.parse import urlparse
    

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
URLSOURCE="UrLSoUrCe"
OUT='-'
OUTFILE=None
QUERIES=[]
TOKENS=None
TOKENFILE=None
VERBOSE=False
SCHEMASTRIP=False
FORMAT = "turtle"
FIRSTREPORT=True
EXEC=""
INFORMAT=None

from LoCSRUResponse import LoCSRUResponse
PREPROC=None

SCHEMAONLY="""
prefix schema: <http://schema.org/> 
DELETE {
    ?s ?p ?o.
} WHERE {
    ?s ?p ?o.
    FILTER ( ! (strstarts(str(?p),"http://schema.org") || strstarts(str(?o),"http://schema.org")) )
}"""

def setPreProcess(proc=None):
    global PREPROC
    if not proc:
        return
        
    from LoCSRUResponse import LoCSRUResponse
    if proc == "LoCSRUResponse":
        PREPROC=LoCSRUResponse()
    else:
        print("Unrecognised preprocess function '%s'" % proc)
        sys.exit(1)


def getOut(file=""):
    global OUT, OUTFILE, BATCH, SOURCE, QUERIES, FORMAT, PREPROC
    if OUT == '-' or OUTFILE == '-':
        return sys.stdout
    elif OUTFILE:
        file = "%s/%s" % (OUT,OUTFILE)
    else:
        file = "%s/%s" % (OUT,os.path.basename(file))

    froot = os.path.splitext(file)[0]
    file = froot + EXTS[FORMAT]
        
    report("Output file: %s" % file)
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
    global VERBOSE,FIRSTREPORT
    if not VERBOSE:
        return
    if FIRSTREPORT:
        FIRSTREPORT=False
        print("%s version: %s" % (EXEC,VER))
    print(msg)
                  
    
def main():
    global OUT, BATCH, SOURCE, QUERIES, VERBOSE, FORMAT, TOKENFILE, OUTFILE, EXEC, SCHEMASTRIP
    EXEC = os.path.basename(__file__)
    infiles = []
    query = None
    parser = argparse.ArgumentParser()
    parser.add_argument("-i","--input", required=True, help="Input rdf file | input rdf file URL | input dir")
    parser.add_argument("-b", "--batchload", action='store_true', help="Load all input files then output combination into single output file")
    parser.add_argument("-o","--output", default=".", help="Output directory | - (stdout) [defaults to '.']")
    parser.add_argument("-O","--outfile", help="Overriding output file name")
    parser.add_argument("-f","--format",default="turtle", help="Output format (xml|rdf|n3|turtle|nt|nquads|jsonld)")
    parser.add_argument("-F","--sourceformat", help="Format (xml|rdf|n3|turtle|nt|nquads|jsonld) of input")
    parser.add_argument("-q","--query", help="Source sparql query files | queries dir")
    parser.add_argument("-t","--tokenfile", help="File containing substitute token mappings")
    parser.add_argument("-c","--querycount", type=int, default=1, help="Number of times to iterate through queries")
    parser.add_argument("-s","--schemaonly", action='store_true', help="Only output Schema.org triples")
    parser.add_argument("-p","--preprocess", help="Source preprocess function (eg. LoCSRUResponse)")
    parser.add_argument("-v", action='store_true', help="Verbose output")
    parser.add_argument("-V", "--version", action='store_true', help="Version")
    args = parser.parse_args()
    
    if args.version:
        print("%s version: %s" % (EXEC,VER))
    
    setPreProcess(args.preprocess)
        
    VERBOSE = args.v
    BATCH= args.batchload
    if args.schemaonly:
        SCHEMASTRIP=True
    TOKENFILE=args.tokenfile
    INFORMAT=args.sourceformat
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
    
        
    OUT = args.output
    OUTFILE = args.outfile
    
    if not os.path.exists(OUT):
        report("Creating directory %s" % OUT)
        os.makedirs(OUT)
            
    report("BATCH Mode: %s" % BATCH)
        
    
    if args.format:
        FORMAT = args.format
        outf = FORMAT
        if FORMAT == "xml" or FORMAT == "rdf":
            outf = "pretty-xml"

    if FORMAT not in EXTS:
        print("Unsupported format: %s" % FORMAT)
        sys.exit(1)

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
                if PREPROC:
                    data = PREPROC.process(f)
                    g.parse(data=data,format=INFORMAT)
                else:
                    g.parse(f)
                report("Loaded : %s" % f)
            except Exception as e:
                print("Parse error for source '%s': \n%s" % (f,e))
                sys.exit(1)
            g.bind('schema', 'http://schema.org/')
        if not OUTFILE:
            outstub = "output"
        else:
            outstub = OUTFILE
        runQueries(g, queryCount=queryCount)
        outGraph(g,outf,outstub)

    else: #Single mode
        for f in infiles:
            outstub = f
            isUrl = False
            u = urlparse(f)
            if u.scheme and u.netloc:
                isUrl = True
                SOURCE = URLSOURCE
                outstub = os.path.basename(u.path)
                report("URL Source")
            elif not os.path.exists(f):
                report("No such file: %s" % f)
                continue
            g = rdflib.Graph()
            try:
                if PREPROC:
                    data = PREPROC.process(f)
                    g.parse(data=data,format=INFORMAT)
                else:
                    g.parse(f,format=INFORMAT)
                report("Loaded: %s" % f)
            except Exception as e:
                print("Parse error for source '%s': \n%s" % (f,e))
                sys.exit(1)
            g.bind('schema', 'http://schema.org/')
            runQueries(g, queryCount=queryCount)
            outGraph(g,outf, outstub)
            
def runQueries(g,queryCount=1):
    count=0
    while count < queryCount:
        count+=1
        if queryCount > 1:
            report("Queries pass No: %s" % (count))
        for q in sorted(QUERIES):
            report("Running query: %s" % q)
            runQueryFile(graph=g,query=q)
        
                
def outGraph(g, outf, outstub="output"):
    global SCHEMASTRIP
    if SCHEMASTRIP:
        report("Stripping none Schema.org triples")
        runQuery(graph=g,queryText=SCHEMAONLY)
    outdata = g.serialize(format = outf,auto_compact=True).decode('utf-8')
    if outf == 'jsonld':
        outdata = simplyframe(outdata)
    out = getOut(file=outstub)
    out.write(outdata)
    out.close()
    
def simplyframe(jsl):
        data = json.loads(jsl)
        items, refs = {}, {}
        for item in data['@graph']:
            itemid = item.get('@id')
            if itemid:
                items[itemid] = item
            for vs in item.values():
                for v in [vs] if not isinstance(vs, list) else vs:
                    if isinstance(v, dict):
                        refid = v.get('@id')
                        if refid and refid.startswith('_:'):
                            refs.setdefault(refid, (v, []))[1].append(item)
        for ref, subjects in refs.values():
            if len(subjects) == 1:
                ref.update(items.pop(ref['@id']))
                del ref['@id']
        items = flattenIds(items)
        data['@graph'] = items
        return json.dumps(data, indent=2)
        
def flattenIds(node):
        ret = node
        if isinstance(node, dict):
            if len(node) == 1:
                id = node.get("@id", None)
                if id:
                    return id #Return node @id instead of node
            for s, v in node.items():
                node[s] = flattenIds(v)

        elif isinstance(node,list):
            lst = []
            for v in node:
                lst.append(flattenIds(v))
            ret = lst
        return ret



if __name__ == "__main__":
    main()