#!/usr/bin/env python
###################################################################
# 
# schemaise.py
# Version: 2.0
#
# Script for processing RDF data, which has been tweaked a little to make it particularly useful to Bibframe2Schema.org.
#  
#  Its operation is controlled by passing command-line parameters:
# 
#   --input Source input RDF file, or directory containing one or more RDF files. Acceptable formats (RDF/XML, json-ld, turtle, nt).
#   --output Output file (for single file) or directory for multiple files.  
#   --format Serialisation format fot output files (xml|rdf|n3|turtle|nt|nquads|jsonld) - influences output file name extension. Default format turtle.
#   --query File, or directory of files, containing SPARQL query scripts to process imported RDF data to produce output RDF data.
#   --bindings key-value pairs for SPARQL bindings
#   --querycount Number of times to process query scripts before outputting resultant data. Default count 1.
#   --schemaonly Only ouput triples that contain a URI from the Schema.org vocabulary as a subject or predicate.
#   -v Run in verbose mode.
#
# Copyright (c) 2020,2023 Richard Wallis - Data Liberate <https://dataliberate.com>
# Originator Richard Wallis
# Licenced under Creative Commons Licence CC0 <https://creativecommons.org/publicdomain/zero/1.0>
#
###################################################################
VER="2.0"
import sys
import os
import re
import datetime
import argparse
import urllib
import rdflib
import json
import importlib

for path in [os.getcwd(),"./scripts"]:
    sys.path.insert(1, path)  # Pickup libs from local  directories


if sys.version_info.major == 2:
    from urlparse import urlparse
elif sys.version_info.major == 3:
    from urllib.parse import urlparse

from rdflib.parser import Parser
from rdflib.namespace import XSD
from rdflib.serializer import Serializer
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parser import parseUpdate
from rdflib.plugins.sparql.algebra import translateQuery, translateUpdate
from rdflib.util import guess_format
from concurrent.futures import ThreadPoolExecutor, as_completed

#rdflib.plugin.register("jsonld", Parser, "rdflib_jsonld.parser", "JsonLDParser")
#rdflib.plugin.register("jsonld", Serializer, "rdflib_jsonld.serializer", "JsonLDSerializer")


EXTS = {"xml": ".xml",
        "rdf": ".rdf",
        "turtle": ".ttl",
        "nt": ".nt",
        "nquads": ".nq",
        "json-ld": ".jsonld"}

BATCH = True
SOURCE="."
URLSOURCE="UrLSoUrCe"
OUT='-'
OUTFILE=None
QUERIES=[]
QUERYDEFS={}
VERBOSE=False
SCHEMASTRIP=False
FORMAT = "turtle"
FIRSTREPORT=True
EXEC=""
INFORMAT=None
DUMPQUERY=False

PREPROC=None
POSTPROC=None

SCHEMAONLY="""
prefix schema: <https://schema.org/> 
DELETE {
    ?s ?p ?o.
} WHERE {
    ?s ?p ?o.
    FILTER (( ! (strstarts(str(?p),"http://schema.org") || strstarts(str(?o),"http://schema.org")) ) && ( ! (strstarts(str(?p),"https://schema.org") || strstarts(str(?o),"https://schema.org")) ) )
}"""


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
    return open(file,"w", encoding='utf8')

def runQueryFile(graph=None,query=None):
    if not graph or not query:
        return
    q = QUERYDEFS.get(query,None)
    if not q:
        q = queryDef(query)
    if q.update:
        graph.update(q.text,initBindings=getBindings())
    else:
        graph.query(q.compiled,initBindings=getBindings())

def runQuery(graph=None,queryText=None):
    if not graph or not queryText:
        return
    if re.search('INSERT',queryText, re.IGNORECASE) or re.search('DELETE', queryText, re.IGNORECASE):
        graph.update(queryText,initBindings=getBindings())
    else:
        graph.query(queryText,initBindings=getBindings())

BINDINGSTORE=None
def getBindings():
    global BINDINGSTORE, EXBINDINGS
    if not BINDINGSTORE:
        bindings = {}

        bindings['TODAY'] =  rdflib.Literal(datetime.datetime.utcnow().strftime("%Y-%m-%d"),datatype=XSD.date)
        bindings['NOW'] = rdflib.Literal(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),datatype=XSD.dateTime)

        urir = re.compile(r'^<(http.*)>$')

        for b in EXBINDINGS:
            val = EXBINDINGS[b].strip()
            uri = None
            match = urir.search(val)
            if match:
                uri = match.group(1)
            if uri:
                bindings[b] = rdflib.URIRef(uri)
            else:
                bindings[b] = rdflib.Literal(val)
        BINDINGSTORE = bindings

    return BINDINGSTORE  
        
def report(msg):
    global VERBOSE,FIRSTREPORT
    if not VERBOSE:
        return
    if FIRSTREPORT:
        FIRSTREPORT=False
        print("%s version: %s" % (EXEC,VER))
    print(msg)
                  
class storeBindings(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        d = getattr(namespace, self.dest) or {}
        for value in values:
            if value:
                kv = value.split('=', 1)
                k = kv[0].strip() # we remove blanks around keys, as is logical
                d[k] = kv[1] if len(kv) > 1 else None
        setattr(namespace, self.dest, d)

def main():
    global OUT, BATCH, SOURCE, QUERIES, VERBOSE, FORMAT, OUTFILE, EXEC, SCHEMASTRIP, DUMPQUERY, EXBINDINGS, PREPROC, POSTPROC
    EXEC = os.path.basename(__file__)
    infiles = []
    query = None
    parser = argparse.ArgumentParser()
    parser.add_argument("-i","--input", required=True, help="Input rdf file | input rdf file URL | input dir")
    parser.add_argument("-b", "--batchload", action='store_true', help="Load all input files then output combination into single output file")
    parser.add_argument("-Q", "--outputrawquery", action='store_true', help="Output to <sdout> query script contents with tokens substituted")
    parser.add_argument("-o","--output", default=".", help="Output directory | - (stdout) [defaults to '.']")
    parser.add_argument("-O","--outfile", help="Overriding output file name")
    parser.add_argument("-f","--format",default="turtle", help="Output format (xml|rdf|n3|turtle|nt|nquads|json-ld)")
    parser.add_argument("-F","--sourceformat", help="Format (xml|rdf|n3|turtle|nt|nquads|jsonld) of input")
    parser.add_argument("-q","--query", help="Source sparql query files | queries dir")
    parser.add_argument("-c","--querycount", type=int, default=1, help="Number of times to iterate through queries")
    parser.add_argument("-s","--schemaonly", action='store_true', help="Only output Schema.org triples")
    parser.add_argument("-p","--preprocess", help="Source preprocess function (eg. LoCSRUResponse)")
    parser.add_argument("-P","--postprocess", help="Graph postprocess function")
    parser.add_argument("-v", action='store_true', help="Verbose output")
    parser.add_argument("-V", "--version", action='store_true', help="Version")
    parser.add_argument("-T","--threads", type=int, default=1, help="Number of threads")
    parser.add_argument('-B', '--bindings',action=storeBindings,type=str,nargs='*', default=[],
            dest="bindings",metavar="LABEL=VALUE",
            help="Key-value pairs for SPARQL bindings"
            "(do not put spaces before or after the = sign). "
            "If a value contains spaces, you should define "
            "it with double quotes: "
            'foo="this is a sentence". Note that '
            "values treated as URIs if of the form <httpuri>, treated as strings.",
        )
    args = parser.parse_args()
    VERBOSE = args.v

    THREADS = args.threads
    
    if args.version:
        report("%s version: %s" % (EXEC,VER))

    if args.outputrawquery:
       DUMPQUERY = True
    
    if args.preprocess:
        try:
            mod = importlib.import_module(args.preprocess)
            PREPROC = getattr(mod, "process")
            if not PREPROC:
                print("No process() function in %s lib" % args.preprocess)
                sys.exit(1)
        except Exception as e:
            print("Error loading preprocess function from lib %s - %s" % (args.preprocess,e))
            sys.exit(1)
    
    if args.postprocess:
        try:
            mod = importlib.import_module(args.postprocess)
            postProcess = getattr(mod, "process")
            if not POSTPROC:
                print("No process() function in %s lib" % args.postprocess)
                sys.exit(1)
        except Exception as e:
            print("Error loading postprocess function from lib %s" % args.postprocess)
            sys.exit(1)
        
    report("Rdflib Ver: %s " % rdflib.__version__)
    BATCH= args.batchload
    if args.schemaonly:
        SCHEMASTRIP=True
    INFORMAT=args.sourceformat
    queryCount = args.querycount
    EXBINDINGS = args.bindings
    
    
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
        
    for q in QUERIES:
        queryDef(q)
        
    
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
                    fmt = INFORMAT
                    if not fmt:
                        fmt = rdflib.util.guess_format(f)
                    g.parse(data=data,format=fmt)
                else:
                    g.parse(f)
                report("Loaded : %s" % f)
            except Exception as e:
                print("Parse error for source '%s': \n%s" % (f,e))
                continue
                #sys.exit(1)
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
                    data = PREPROC(f)
                    fmt = INFORMAT
                    if not fmt:
                        fmt = rdflib.util.guess_format(f)
                    g.parse(data=data,format=fmt)
                else:
                    g.parse(f,format=INFORMAT)
                report("Loaded: %s" % f)
            except Exception as e:
                print("Parse error for source '%s': \n%s" % (f,e))
                sys.exit(1)
            g.bind('schema', 'https://schema.org/')
            runQueries(g, queryCount=queryCount)
            outGraph(g,outf, outstub)



class queryDef():
    def __init__(self,query):
        global args
        self.query = query
        with open(query, 'r') as myfile:
          self.text = myfile.read()
        if DUMPQUERY:
            print("Query '%s':" % self.query)
            print(self.text)
        self.update = False
        if re.search('INSERT', self.text, re.IGNORECASE) or re.search('DELETE', self.text, re.IGNORECASE):
            self.update = True
            #self.compiled = translateUpdate(parseUpdate(self.text))
        else:
            self.compiled = prepareQuery(self.text)
        QUERYDEFS[self.query] = self
        
        
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
        try:
            report("Stripping none Schema.org triples")
            g.update(SCHEMAONLY)

        except Exception as e:
            print("Error when stripping schema: %s" % e)

    g = postProcess(g,outstub)

    try:
        if isinstance(g, rdflib.Dataset):
            fix = rdflib.ConjunctiveGraph()
            for graph in g.contexts():
                for (s,p,o) in graph:
                    fix.add((s,p,o, graph.identifier))
            g = fix

        outdata = g.serialize(format = outf,auto_compact=True)
        if outf == 'jsonld':
            outdata = simplyframe(outdata)
    except Exception as e:
        print("Serialization error for source '%s': \n%s" % (outf,e))
        return
            
    out = getOut(file=outstub)
    out.write(outdata)
    out.close()

def postProcess(graph,id):
    global POSTPROC
    if not POSTPROC:
        return graph
    try:
        return POSTPROC(graph,id,baseuri)
    except Exception as e:
        print("Error processing 'process()' function from postprocess module: %s" % e)
        return
    
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
