#!/usr/bin/env python

import HighEagle as HE
import argparse
import shutil
import EagleTools

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix eagle files to make them dtd conforming")
    parser.add_argument("--file", required=True,  type=str, nargs='+', dest='file', help="files to process")
    parser.add_argument("--layers", required=False,  type=str, nargs=1, dest='layers', help="If present, add these layers")
    parser.add_argument("--force", required=False,  action="store_true", dest='force', help="Overwrite layers in file.")
    args = parser.parse_args()
    
    if args.layers:
        layers = HE.LibraryFile.from_file(args.layers[0])

    for f in args.file:

        ef = HE.EagleFile.from_file(f)

        if args.layers:
            EagleTools.normalizeLayers(ef, layers, force=args.force)

            #print EagleTools.ScanLibraryReferences(ef).go().get_referenced_efps()
            
        ef.write(f)