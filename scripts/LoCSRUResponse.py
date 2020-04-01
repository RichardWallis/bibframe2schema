#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import urllib
import xml.dom.minidom

class LoCSRUResponse:
    def process(self,source):
        ret = None
        try:
            doc = xml.dom.minidom.parse(urllib.urlopen(source))
            rdfnodes = doc.getElementsByTagNameNS("http://www.w3.org/1999/02/22-rdf-syntax-ns#","RDF")
            if not rdfnodes:
                print("LoCSRUResponse - XML Load error: Cannot identify RDF:rdf node in source")
            else:
                ret = rdfnodes[0].toxml()
        except Exception as e:
            print("LoCSRUResponse - XML Load error: %s" % e)
        return ret