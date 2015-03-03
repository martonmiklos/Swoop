from lxml import etree as ET
import eagleDTD
import StringIO
import logging as log
import copy
import os

class EagleFormatError(Exception):
    def __init__(self, text=""):
        self.text = text
    def __str__(self):
        return self.text

class HighEagleError (Exception):
    def __init__(self, text):
        self.text = text
    def __str__(self):
        return self.text

class EagleFilePart(object):
    """Base class for all eagle tag objects.  It provides fallback implementations
    of core features, facilities for navagating the part tree, and provides the
    :code:`parent` attribute.

    """
    
    def __init__(self):
        self.parent = None

    def get_file(self):
        """
        Get the :class:`EagleFile` containing this object.

        :rtype: :class:`EagleFile`

        """
        r = self.get_root()
        if isinstance(r, EagleFile):
            return r
        else:
            return None

    def get_parent(self):
        """
        Get this object's parent.

        :rtype: :class:`EagleFilePart`
        """
        return self.parent

    @classmethod
    def from_et (cls, et):
        """
        Parse the part from an Element Tree

        :rtype: :class:`EagleFilePart`
        """
        raise NotImplementedError()
    
    def get_et ():
        """
        Generate an element tree that represents the :code:`EagleFilePart`.

        :rtype: :class:`etree.ElementTree`

        """
        raise NotImplementedError()

    def get_root(self):
        """ 
        Find the root of this :class:`EagleFilePart` tree.

        :rtype: :class:`EagleFilePart`

        """
        if self.get_parent() is not None:
            return self.get_parent().get_root()
        else:
            return self

    def clone(self):
        """
        Clone the :class:`EagleFilePart`.  It should be identical to the orginial, except that the parent should be :code:`None`.

        :rtype: :class:`EagleFilePart`
        """
        raise NotImplementedError()

    def get_children(self):
        """
        Return a list of all the :code:`EagleFilePart` children of this :code:`EagleFilePart`

        :rtype: List of :class:`EagleFilePart`

        """
        raise NotImplementedError()

    def check_sanity(self):
        """
        Perform a (recursive) sanity check on this :code:`EagleFilePart`
        
        :rtype: :code:`None`
        """
        for i in self.get_children():
            #print "."
            if i.parent != self:
                raise HighEagleError("Parent pointer mismatch.  Child = " + str(i) + "; child.parent = " + str(i.parent) + "; Parent = " + str(self) )
            i.check_sanity()

def parseByType(efp, attrType, s):
    if s is not None:
        if attrType == "str":
            r = s
        elif attrType == "int":
            r = int(s)
        elif attrType == "float":
            r = float(s)
        elif attrType == "bool":

            if s.upper() in ["YES"]:
                r = True
            elif s.upper() in ["NO"]:
                r = False
            else:
                raise HighEagleError("Invalid eagle bool value '" + s +"' in child of " + str(efp))
        elif attrType == "constant_bool":
            r = (s != "no")
        elif attrType == "layer_string":
            r = efp.get_file().layer_number_to_name(int(s))
        else:
            raise HighEagleError("Unknown attr type '" + attrType + "'")
        assert r is not None
    else:
        r = None
    
    return r

def unparseByType(efp, attrType, v):
    if v is not None:
        if attrType == "str":  # Doing nothing to strings lets us handle weird
                               # unicode characters.
            r = v 
        elif attrType in ["int", "float"]:
            r = str(v)
        elif attrType == "bool":
            if v:
                return "yes"
            else:
                return "no"
        elif attrType == "constant_bool":
            if not v:
                r = "no"
            else:
                r = None
        elif attrType == "layer_string":
            r = efp.get_file().layer_name_to_number(v)
        else:
            raise HighEagleError("Unknown attr type '" + attrType + "'")

        if attrType != "constant_bool":
            assert r is not None
    else:
        r = None
    
    return r
        
            
class EagleFile(EagleFilePart):
    """
    Base class for Eagle files.  Handles opening, parsing, validation, associated errors, writing, and layers.
    """

    # A validator for element tree representations of eagle files.
    DTD = ET.DTD(StringIO.StringIO(eagleDTD.DTD))

    def __init__ (self):
        """
        Construct an empty :class:`EagleFile`.
        """
        EagleFilePart.__init__(self)
        self.filename= None
        self.root = None
        self.tree = None
        self.layers = {}
        self.layersByName = {}

        
    def validate(self):
        """
        Check that this file conforms to the eagle DTD. Return True, if it does, False otherwise.

        :rtype: Bool
        """
        et = self.get_et()
        v = EagleFile.DTD.validate(et)
        
        if not v:
            log.warning("Eagle file opened as '" + str(self.filename) +"' is invalid: " + str(EagleFile.DTD.error_log.filter_from_errors()[0]))
        else:
            log.info("Eagle file opened as '" + self.filename +"' parsed to valid Eagle data.")

        for t in et.findall(".//*"):
            for a in t.attrib.values():
                if a == str(None):
                    log.warning("Eagle file opened as '" + str(self.filename) +"' has 'None' attribute value")
                    return False
        
        return v

    @staticmethod
    def from_file (filename, bestEffort = True):
        """
        Loads a Eagle file from a .sch, .lbr, or .brd file. 

        :param bestEffort: If :code:`True`, load the file even if it doesn't conform to the DTD.
        
        :rtype: :class:`BoardFile`, :class:`LibraryFile`, or :class:`SchematicFile`
        """
        try:
            tree = ET.parse(filename)
        except ET.XMLSyntaxError as e:
            raise EagleFormatError("Eagle file '" + str(filename) +"' doesn't look like XML eagle file.  Try resaving with a newer version of eagle.")
        
        root = tree.getroot()

        v = EagleFile.DTD.validate(root)
        if not v:
            if bestEffort:
                log.warning("Eagle file opened as '" + str(filename) +"' is invalid on disk: " + str(EagleFile.DTD.error_log.filter_from_errors()[0]))
            else:
                raise EagleFormatError("Eagle file opened as '" + str(filename) +"' is invalid on disk: " + str(EagleFile.DTD.error_log.filter_from_errors()[0]))
                
        if filename[-4:] == ".sch":
            ef = SchematicFile.from_et(root, None)
        elif filename[-4:] == ".brd":
            ef = BoardFile.from_et(root, None)
        elif filename[-4:] == ".lbr":
            ef = LibraryFile.from_et(root, None)#,filename=filename)
        else:
            raise HighEagleError("Unknown file suffix: '" + filename[-4:] + "'")
        ef.filename = filename
        ef.root = root
        ef.tree = tree
        #ET.dump(ef.root)
        ef.check_sanity()
        return ef

    @staticmethod
    def from_file_by_type(filename, ftype):
        n = EagleFile.from_file(filename)
        if not isinstance(n, ftype):
            raise HighEagleError("File is '" + filename + "' is not " + ftype.__name__)
        return n

    def write (self, filename):
        """
        Exports the Schematic to an EAGLE schematic file.
        
        :param filename: Filename for output.
        
        :rtype: :code:`None`
        """

        header="""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE eagle SYSTEM "eagle.dtd">
"""
        self.check_sanity()
        if not self.validate():
            f = open(filename + ".broken.xml", "w")
            f.write(header + ET.tostring(ET.ElementTree(self.get_et()),pretty_print=True))
            raise HighEagleError("element tree does not validate" + str(EagleFile.DTD.error_log.filter_from_errors()[0]))
        else:
            f = open(filename, "w")
            f.write(header+ET.tostring(ET.ElementTree(self.get_et()),pretty_print=True))

    def add_layer (self, layer):
        """
        Add a layer to this file.
        
        :param layer: The :class:`Layer` to add.

        :rtype: :code:`None`

        """
        assert isinstance(layer, Layer)
        #print str(self) +" " + str(int(layer.number))
        self.layers[int(layer.number)] = layer
        self.layersByName[layer.name] = layer
        layer.parent = self

    def get_layers(self):
        """
        Get a map of names to Layer objects
        
        :rtype: Map of :code:`EagleFilePart` keyed by layer name.

        """
        return self.layersByName

    def get_layersByNumber(self):
        """
        Get a map of numbers to Layer objects.

        :rtype: Map of :code:`EagleFilePart` keyed by layer number.
        """
        return self.layers

    # def get_flippedLayer(self, l):
    #     if (isinstance(l, str)):
    #         origName = l
    #         if l[0] == "t":
    #             l = "b" + l[1:]
    #         elif l[0] == "b":
    #             l = "t" + l[1:]
    #         elif l == "Top":
    #             l = "Bottom"
    #         elif l == "Bottom":
    #             l = "Top"
    #         if l not in self.layersByName:
    #             raise HighEagleError("Tried to flip layer '" + origName + "', but '" + l + "' doesn't exist")
    #         return name
    #     elif (isinstance(l,int)):
    #         if l in self.layers:
    #             return self.get_flippedLayer(self, self.layers[l]).number
    #         else:
    #             raise HighEagleError("Can't find layer number " + number)
    #     elif (isinstance(l,Layer)):
    #         if l.name in self.layersByName:
    #             return self.layersByName[get_flippedLayer(l.name)]
    #         else:
    #             raise HighEagleError("Can't find layer '" + l.name +"' in this file")

    def parse_layer_number(self, num):
        """ 
        Give a layer number, return the name.  Specifically for use in parsing.  You probably shouldn't call this.  Use :func:`layer_number_to_name` instead.

        :rtype: :class:`Layer` 
        """
        if num is None:
            return None
        return self.layer_number_to_name(num)

    def unparse_layer_name(self, name):
        """ 
        Give a layer number, return the name.  Specifically for use in parsing.  You probably shouldn't call this.  Use :func:`layer_name_to_number` instead.
        
        :rtype: :class:`Layer` 
        """
        if name is None:
            return None
        return self.layer_name_to_number(name)
    
    def layer_number_to_name(self, num):
        """
        Given a layer number, return the name.

        :rtype: :class:`Layer` 
        """
        n = int(num)
        if n not in self.layers:
            raise HighEagleError("No layer number " + str(n) +" in " + str(self.filename))
        return self.layers[n].name

    def layer_name_to_number(self, name):
        """
        Given a layer name, return the number.

        :rtype: :class:`Layer` 
        """
        #print type(name)
        #print name
        assert type(name) is str
        if name not in self.layersByName:
            raise HighEagleError("No layer named '" + name + "' in " + str(self.filename))
        return self.layersByName[name].number

    def remove_layer(self, layer):
        """
        Remove a layer.
        
        :param layer: :class:`Layer` object, layer name, or layer number that should be deleted.
        
        :rtype: :code:`None`
        """
        if type(layer) is str:
            l = self.layersByName[layer]
            self.remove_layer(l)
        elif type(layer) is int:
            l = self.layers[layer]
            self.remove_layer(l)
        elif isinstance(layer, Layer):
            self.layersByName[layer.name].parent = None
            del self.layersByName[layer.name]
            del self.layers[int(layer.number)]
        else:
            raise HighEagleError("Invalid layer spec: " + str(layer))
            
    # def get_manifest(self):
    #     raise NotImplementedError("Manifest for " + str(type(self)))

    def find_library_by_name(self, l):
        """
        Lookup a library by name and return it.

        :param l: Library name.
        :rtype: :class:`Library` or :code:`None` if the library is not present.
        """
        return self.libraries.get(l)

    
def smartAddSubTags(root, path):
    """
    Add tags as need to create a container for the contents of an xpath.

    :rtype: :code:`None`
    """
    pathSegments = path.split("|")[0].replace("./","").split("/")
    target = root
    for p in pathSegments[0:-1]:
        new_target = target.find(p)
        if new_target is None:
            #print "created  " + p
            target = ET.SubElement(target,p)
        else:
            target = new_target
    return target


# def parse_constant(t,s):
#     return s != "no"

# def unparse_constant(t,s):
#     if not s:
#         return "no"
#     else:
#         return None

classMap = {}
    

#{% for tag in tags %}

#{%if not tag.customchild %}
#{% set classname = tag.classname %}
#{% else %}
#{% set classname = "Base_" + tag.classname %}
#{%endif%}

class {{classname}}({{tag.baseclass}}):
    """
    Class representing the contents of a <{{tag.tag}}> in Eagle files.
    """
    def __init__(self,
                 #{%for a in tag.attrs %}
                 {{a.name}}=None,
                 #{%endfor%}
                 #{%for l in tag.sections %}
                 {{l.name}}=None,
                 #{%endfor%}
                ):
        """
        Construct an empty :class:`{{classname}}` object.
        """

        {{tag.baseclass}}.__init__(self)
        
        #{%for a in tag.attrs %}
        #if {{a.name}} is not None:
        self.{{a.name}} = {{a.name}}
        #{%if a.required %}
        #else:
        #    self.{{a.name}} = None
        #{%endif%}    

        #{%endfor%}

        #{%for l in tag.lists %}
        if {{l.name}} is None:
            self.{{l.name}} = []
        else:
            self.{{l.name}} = {{l.name}}
        #{%endfor%}

        #{%for m in tag.maps %}
        if {{m.name}} is None:
            self.{{m.name}} = {}
        else:
            self.{{m.name}} = {{m.name}}
        #{%endfor%}

        #{%for s in tag.singletons%}
        self.{{s.name}} = {{s.name}}
        #{%endfor%}

        #{%if tag.preserveTextAs != "" %}
        self.{{tag.preserveTextAs}} = ""
        #{%endif%}

    @classmethod
    def from_et(cls,root,parent):
        """
        Create a {{tag.classname}} from a {{tag.tag}} element.
        
        :param root: The element tree tree to parse.
        :param parent: :class:`EagleFilePart` that should hold the resulting :class:`EagleFilePart`
        :rtype: :class:`{{tag.classname}}`
        """
        
        if root.tag != "{{tag.tag}}":
            raise EagleFormatError("Tried to create {{tag.tag}} from " + root.tag)

        ## Call the constructor
        n = cls(
            #{%for a in tag.attrs%}
            {{a.name}}={{a.parse}}(parent, "{{a.vtype}}", root.get("{{a.xmlName}}")),
            #{%endfor%}
        )
        #print "getting {{tag.tag}}"
        #{%for a in tag.attrs%}
        #{%if a.parse != "" %}
        #print "got {{a.name}} {{a.xmlName}}= " + str({{a.parse}}(root.get("{{a.xmlName}}")))
        #print n.{{a.name}}
        #{%else%}
        #print "got {{a.name}} {{a.xmlName}}= " + str(root.get("{{a.xmlName}}"))
        #{%endif%}
        #print n.{{a.name}}
        #{%endfor%}
        n.parent = parent

        ### populate the maps by searching for elements that match xpath and generating objects for them.
        
        #{%for m in tag.maps%}
        for c in root.xpath("{{m.xpath}}"):
            n.add_{{m.accessorName}}(classMap[c.tag].from_et(c, n))
            #n.{{m.name}}[c.get("name")] =  classMap[c.tag].from_et(c, n)
            
        #{%endfor%}

        ### Do the same for the lists

        #{%for l in tag.lists %}
        for c in root.xpath("{{l.xpath}}"):
            n.add_{{l.accessorName}}(classMap[c.tag].from_et(c,n))
            #n.{{l.name}} = [classMap[c.tag].from_et(c,n) for 
        #{%endfor%}

        ### And the singletons
        
        #{%for s in tag.singletons %}
        x = root.xpath("{{s.xpath}}")
        if len(x) is not 0:
            n.set_{{s.accessorName}}(classMap[x[0].tag].from_et(x[0],n))
        #{%endfor%}

        ### And, finally, if the objects wants the text from the tag.
        
        #{%if tag.preserveTextAs != "" %}
        n.{{tag.preserveTextAs}} = root.text
        #{% endif %}

        #{%for a in tag.attrs%}
        #{%if a.parse != "" %}
        #print "got {{a.name}}= " + str({{a.parse}}(root.get("{{a.xmlName}}")))
        #{%else%}
        #print "got {{a.name}}= " + str(root.get("{{a.xmlName}}"))
        #{%endif%}
        #{%endfor%}
        return n


    def get_et(self):
        """
        Generate a <{{tag.tag}}> element tree for a :class:`{{tag.classname}}`.
        
        :rtype:  :class:`ElementTree`.
        
        """
        r = ET.Element("{{tag.tag}}")

        ### Set the tag attributes 
        
        #{%for a in tag.attrs%}

        ## Unparse the values.

        v = {{a.unparse}}(self, "{{a.vtype}}", self.{{a.name}})
        #print v
        #print type(v)
        #print "{{a.unparse}}"
        #{%for a in tag.attrs%}
        #print "setting {{a.xlName}}= " + str(v)
        #{%endfor%}

        ## For required attributes None becomes "".  For optional attributes, we just leave the attribute out.
        if v is not None:
            r.set("{{a.xmlName}}", v)
        #{%if a.required %}
        else:
            r.set("{{a.xmlName}}", "")
        #{%endif%}

        #{%endfor%}

        ### process the sections in order.  They have to be in section order,
        ### because eagle files are order dependent.
        
        #{%for l in tag.sections%}

        ## For some tags, Eagle generates empty tags when there's no contant
        ## rather than just leaving the tag out.  We mark these with
        ## Tag.requireTag in GenerateHighEagle.py and force their generation
        ## here.
        
        #{%if l.requireTag %}
        smartAddSubTags(r, "{{l.xpath}}")
        #{%endif%}

        #{%if l.type == "List" %}

        ## add a list.

        if len(self.{{l.name}}) is not 0:
            target = smartAddSubTags(r, "{{l.xpath}}")
            target.extend([i.get_et() for i in self.{{l.name}}])
        #{%elif l.type == "Map" %}

        ## add a map.
        
        if len(self.{{l.name}}) is not 0:
            target = smartAddSubTags(r, "{{l.xpath}}")
            target.extend([i.get_et() for i in self.{{l.name}}.values()])
        #{%else%}

        ## or add a map.
        
        if self.{{l.name}} is not None:
            target = smartAddSubTags(r, "{{l.xpath}}")
            target.append(self.{{l.name}}.get_et())
        #{%endif%}
        #{%endfor%}

        ## set the text, if its needed.
        
        #{%if tag.preserveTextAs != "" %}
        r.text = self.{{tag.preserveTextAs}}
        #{% endif %}
        return r

    def clone(self):
        """
        Recursively clone this :code:`{{tag.classname}}`.  It will be identical to the original, but it's parent will :code:`None`.
        
        :rtype: :class:`{{tag.classname}}`
        """
        n = copy.copy(self)
        #{%for m in tag.maps%}
        n.{{m.name}} = {}
        for x in self.{{m.name}}.values():
            n.add_{{m.accessorName}}(x.clone())
        #{%endfor%}
        #{%for l in tag.lists %}
        n.{{l.name}} = []
        for x in self.{{l.name}}:
            n.add_{{l.accessorName}}(x.clone())
        #{%endfor%}
        #{%for s in tag.singletons %}
        if n.{{s.name}} is not None:
            n.{{s.name}} = self.{{s.name}}.clone()
        #{%endfor%}
        n.parent = None
        return n

    ### Getters/Setters for attribute values

    #{%for a in tag.attrs%}
    def get_{{a.accessorName}}(self):
        """ Return the value of :code:`{{a.name}}` for this :class:`{{tag.classname}}`.  This corresponds to the :code:`{{a.name}}` attribute of a :code:`<{{tag.tag}}>` in an Eagle file.
        
        :rtype: :code:`{{a.vtype}}`
        """
        return self.{{a.name}}

    def set_{{a.accessorName}}(self,v):
        """ Set the value of :code:`{{a.name}}` for this  :class:`{{tag.classname}}`.  This corresponds to the :code:`{{a.name}}` attribute of a :code:`<{{tag.tag}}>` in an Eagle file.

        :param v: :class:`EagleFilePart` to set.

        :rtype: :code:`None`
        """
        self.{{a.name}} = v
    #{%endfor%}

    ### Adder/getter/lookup for lists
    
    #{%for l in tag.lists%}
    #{%if not l.suppressAccessors %}
    def add_{{l.accessorName}}(self, s):
        """ Add a :code:`{{l.accessorName}}` to this :class:`{{tag.classname}}`.

        :rtype: :code:`None`
        """
        self.{{l.name}}.append(s)
        s.parent = self
    def get_nth_{{l.accessorName}}(self, n):
        """ get then nth :code:`{{l.accessorName}}` from  this  :class:`{{tag.classname}}`.
        
        :param n: Index of the item to return.

        :rtype: :class:`EagleFilePart`
        """
        return self.{{l.name}}[n]
    def get_{{l.name}}(self):
        """ Get the list of :code:`{{l.accessorName}}` from this  :class:`{{tag.classname}}`.

        :rtype: List of :class:`EagleFilePart`
        """
        return self.{{l.name}}
    def clear_{{l.name}}(self):
        """
        Remove all the :code:`{{l.accessorName}}` s from this :class:`{{tag.classname}}`.

        :rtype: :code:`None`
        """
        for efp in self.{{l.name}}:
            efp.parent = None
        self.{{l.name}} = []
        
    #{%else%}
    # {{l.name}} accessor supressed
    #{%endif%}
    #{%endfor%}

    ### Getter/Setter for singletons.

    #{%for l in tag.singletons%}
    #{%if not l.suppressAccessors %}
    def set_{{l.accessorName}}(self, s):
        """ Set {{l.accessorName}} for this  :class:`{{tag.classname}}`.

        :param s: :class:`EagleFilePart` to set.
        :rtype: :code:`None`
        """
        if self.{{l.name}} is not None:
            self.{{l.name}}.parent = None
        self.{{l.name}} = s
        self.{{l.name}}.parent = self

    def get_{{l.accessorName}}(self):
        """ Get {{l.accessorName}} from this  :class:`{{tag.classname}}`.
        
        :rtype: :class:`EagleFilePart`
        """
        return self.{{l.name}}
    #{%endif%}
    #{%endfor%}
    
    ### Add, lookup, and get for maps
    #{%for m in tag.maps%}
    #{%if not m.suppressAccessors %}
    def add_{{m.accessorName}}(self, s):
        """ Add a {{m.accessorName}} to this  :class:`{{tag.classname}}`.

        :param s: :class:`EagleFilePart` to add.
        :rtype: :code:`None`
        """
        self.{{m.name}}[s.{{m.mapkey}}] = s
        s.parent = self

    def get_{{m.accessorName}}(self, key):
        """ Find the {{m.accessorName}} key :code:`key` from this :class:`{{tag.classname}}`.
        
        :param key: key to search by.

        :rtype: :class:`EagleFilePart` or :code:`None`, if there is no such item.
        """
        return self.{{m.name}}[key]

    def get_{{m.name}}(self):
        """ Get map of :code:`{{m.accessorName}}` s from this  :class:`{{tag.classname}}`.
        
        :rtype: dictionary of :class:`EagleFilePart`
        """
        return self.{{m.name}}

    def clear_{{m.name}}(self):
        """
        Remove all the :code:`{{m.accessorName}}` s from this :class:`{{tag.classname}}`.
        
        :rtype: :code:`None`
        """
        for efp in self.{{m.name}}.values():
            efp.parent = None
        self.{{m.name}} = {}

    def remove_{{m.accessorName}}(self, efp):
        """
        Remove a :code:`{{m.accessorName}}` from this :class:`{{tag.classname}}`.
        
        :param efp: Item to remove.

        :rtype: :code:`None`
        """
        del self.{{m.name}}[efp.{{m.mapkey}}]
        efp.parent = None
    #{%endif%}
    #{%endfor%}

    
    def get_children(self):
        """
        Get all the children of this :class:`EagleFilePart`.
        
        :rtype: List of :class:`EagleFilePart`
        """
        r = []

        #{%for l in tag.lists%}
        r = r + self.{{l.name}}
        #{%endfor%}

        #{%for m in tag.maps%}
        r = r + self.{{m.name}}.values()
        #{%endfor%}
        return r

    def dump(self, indent="", increment="   "):
        """
        Recursive debug dump.
        
        :param indent:  Indentation string.  The output will be indented by this much.
        :param increment: This will be appendeded to :code:`indent` on recursive invocations.

        :rtype: :code:`None`
        """
        print indent + str(self.__class__.__name__)
        for c in self.get_children():
            c.dump(indent + "   ")

classMap["{{tag.tag}}"] = {{classname}}
         
#{% endfor %}


class Part (Base_Part):
    """Extra functions for Parts.  Sanity checks, and facilities for find the
    symbols, devices, etc. for a part.

    """
    def __init__(self,
                 name=None,
                 deviceset=None,
                 value=None,
                 library=None,
                 device=None,
                 technology=None,
                 attributes=None,
                 variants=None,
             ):
        Base_Part.__init__(self,
                           name=name,
                           deviceset=deviceset,
                           value=value,
                           library=library,
                           device=device,
                           technology=technology,
                           attributes=attributes,
                           variants=variants)

    # def is_child(self, f):
    #     if f == "schematic":
    #         return False
    #     else:
    #         return EagleFilePart.is_child(self,f)

    def check_sanity(self):
        #assert self.get_device() is not None

        try:
            assert self.find_library() is not None
        except Exception as e:
            raise HighEagleError("Library '" + self.library +  "' missing for " + str(self.name))
        
        try:
            assert self.find_deviceset() is not None
        except Exception as e:
            raise HighEagleError("DeviceSet '" + self.find_library().name + ":" + self.deviceset + "' missing for " + str(self.name))

        try:
            assert self.find_device() is not None
        except Exception as e:
            raise HighEagleError("Device '" + self.find_library().name + ":" + self.find_deviceset().name + ":" + self.device + "' missing for " + str(self.name))
        
        EagleFilePart.check_sanity(self)
        
         
    def find_library(self):
        """
        Get the library that contains this part
        """
        lib = self.get_root().libraries.get(self.library)
        return lib

    def find_deviceset(self):
        """
        Get the deviceset for this part.
        """
        lib = self.find_library();
        deviceset = lib.devicesets.get(self.deviceset)
        return deviceset
        
    def find_device(self):
        """
        Get the library entry for this part
        """
        deviceset = self.find_deviceset()
        device = deviceset.devices.get(self.device)
        return device

    def find_technology(self):
        """
        Get the library entry for this part
        """
        device = self.find_device()
        tech = device.technologies.get(self.technology)
        return tech

    def set_device(self, library=None, deviceset=None, device=None):
        if library is not None:
            self.library = library
        if deviceset is not None:
            self.deviceset = deviceset
        if device is not None:
            self.device = device
        
    def get_package(self):
        """
        Get the library entry for this part
        """
        device = self.find_device();
        lib = self.find_library();
        if device.package is not None:
            package = lib.packages.get(device.package);
        else:
            package = None
        return package

    # def get_library_attributes(self):
    #     """
    #     Get attribute values for this part that come from the library.
    #     """
    #     return {k:v for (k,v) in self.attributes.iteritems() if v.from_library}

    def set_attribute(self,name, value):
        if name in self.attributes:
            self.attributes[name].value = value
        else:
            n = Attribute(name=name, value=value, in_library=False)
            self.add_attribute(n)

    # def get_attribute(self,name):
    #     return self.attributes.get(name).value

    # def remove_attribute(self,name):
    #     self.attributes[name].parent = None
    #     del self.attributes[name]

classMap["part"] = Part


class Attribute (Base_Attribute):
    """Extra functionality for Attributes.  Attributes are used in many places in
    eagle files and they require different attributes in some cases.

    """
    def __init__(self,
                 layer=None,
                 ratio=None,
                 name=None,
                 value=None,
                 y=None,
                 x=None,
                 constant=None,
                 font=None,
                 rot=None,
                 display=None,
                 size=None,
                 in_library=True
                ):
        Base_Attribute.__init__(self,
                                layer=layer,
                                ratio=ratio,
                                name=name,
                                value=value,
                                y=y,
                                x=x,
                                constant=constant,
                                font=font,
                                rot=rot,
                                display=display,
                                size=size)
        self.in_library = in_library


    def __str__(self):
        return self.name + " = '" + self.value + "' [const=" + str(self.constant) + ";lib=" + str(self.from_library) +"]";

    @classmethod
    def from_et (cls, attribute_root, parent):
        n = Base_Attribute.from_et(attribute_root, parent)
        
        if attribute_root.getparent().tag == "technology":
            from_library = True;
        elif attribute_root.getparent().tag == "part":
            from_library = False
        elif attribute_root.getparent().tag == "instance":
            from_library = False
        elif attribute_root.getparent().tag == "element":
            from_library = False
        elif attribute_root.getparent().tag == "attributes":
            from_library = False
        else:
            raise HighEagleError("Unexpectedly found attribute in '" + attribute_root.getparent().tag +"' tag.")

        n.in_library = from_library
        return n
        
    def get_et (self):
        n = Base_Attribute.get_et(self)
        
        if not self.in_library:
            if "constant" in n.attrib:
                del n.attrib["constant"]

        return n

classMap["attribute"] = Attribute

#### Extra methods for DeviceSets

# This converts the deviceset into an external device.  This means that it
# has no associated package.  It can, however, have attributes, and those
# are stored in the "" device.  You can't just delete all the packages,
# since you'd lose the attributes.  This copies them from the first
# package.
def convertToExternal(self):
    if len(self.get_devices()) > 0:
        d = self.get_devices().values()[0]
        for i in self.get_devices().values():
            self.remove_device(i)
        d.name = ""
        d.package = "_EXTERNAL_"
        d.clear_connects()
    else:
        d = Device(name="", package="_EXTERNAL_", technologies=[Technology(name="")])

    self.add_device(d)
    for t in d.get_technologies().values():
        t.add_attribute(Attribute(name="_EXTERNAL_"))

setattr(Deviceset, "convertToExternal", convertToExternal)
        
# class LibraryFile(Base_LibraryFile):
#     """ 
    
#     def __init__(self,
#                  version=None,
#                  settings=None,
#                  grid=None,
#                  layers=None,
#                  library=None,
#                  compatibility=None
#                 ):
#         Base_LibraryFile.__init__(self,
#                                   version,
#                                   settings,
#                                   grid,
#                                   layers,
#                                   library,
#                                   compatibility)
#     @classmethod
#     def from_et (cls, et, filename):
#         """
#         Loads a Library file from an ElementTree.Element representation.
#         """
#         r = Base_LibraryFile.from_et(et)
#         #if r.get_library().name is None:
#         #r.get_library().set_name(os.path.basename(filename)[:-4])
#         return r

#     # def get_library_copy(self):
#     #     return copy.deepcopy(self.library)

    
