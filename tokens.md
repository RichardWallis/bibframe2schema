# bibframe2schema Token Substitution

The ***schemaise.py*** script makes use of a token substitution function when loading *sparql* scripts for processing.

In principle tokens of the format [[*token-name*]] placed within a *sparql* script are replaced with defined values at runtime.  There are a basic set of default defined token values that are supplemented by further user defined token names and values loaded from a token file in JSON format.

## Default Defined Token Values
There are two default tokens:
* [[TODAY]] - Set to the UTC day of operation in the format YYYY-MM-DD
* [[NOW]] - Set to the UTC time of operation in the format YYYY-MM-DD*T*HH:MM:SS*Z*

## User Defined Tokens
Further token substitutions can be enabled by being defined in a token file in JSON format.  The token file is loaded and processed by the *schemaise.py* script by using the *-t* command line option.

An example token file:
```{
    "SDPUBLISHER": "<https://bibframe2schema.org>", 
    "SDLICENSE": "<https://creativecommons.org/publicdomain/zero/1.0>",
    "SDPUBLISHERDESCRIPTION": "<https://bibframe2schema.org> a schema:Organization; schema:name \"Bibframe2Schema.org Community Group\"; schema:url <https://bibframe2schema.org>."
}
```

## Format of Token Values
A token to be replaced can be inserted multiple times anywhere within the *sparql* script.

An unrecognised token, not defined in the token file, will be replaced with an empty string.

Care must be taken to encode the replacement value of a token both so it is valid JSON, and it results in valid SPARQL format when inserted into the *sparql* script. See the above example.

## Tokens in a SPARQL Script
Example extract from a sparql file:
```
   schema:name ?workTitle ;
   schema:sdDatePublished "[[TODAY]]";
   schema:sdLicense [[SDLICENSE]];
   schema:sdPublisher [[SDPUBLISHER]].
```
