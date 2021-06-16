#!/usr/bin/python
import sys
from typing import Optional, List
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from xml.dom import minidom


def bullseyeEventToCobertura(event: str) -> str:
    if event == "full":
        return "100% (2/2)"
    elif event == "true" or event == "false":
        return "50% (1/2)"
    return "0% (0/2)"


def getLinesRate(el: Element) -> str:
    if not float(el.get("cd_total", "0")):
        return "0"
    return str(round(float(el.get("cd_cov")) / float(el.get("cd_total")), 2))


def getBranchRate(el: Element) -> str:
    if not float(el.get("d_cov", "0")):
        return "0"
    return str(round(float(el.get("d_cov")) / float(el.get("d_total")), 2))

def computeComplexity(el: Element) -> str:
    return "0"

def getTagName(el: Element) -> str:
    return el.tag.replace("{https://www.bullseye.com/covxml}", "")


def traverseCovXML(root: Element, parentElement: Element, packages: Element = None, package: Element = None):
    # Cobertura deserialization guts
    # https://github.com/cobertura/cobertura/blob/f986347ec66fe9443c6f48d0995c658ed34c1704/cobertura/src/main/java/net/sourceforge/cobertura/reporting/xml/XMLReport.java
    for item in root:
        if getTagName(item) == "folder":
            parentPath = f"{package.get('_path')}/" if package else ""
            folderPath = f"{parentPath}{item.get('name')}"
            new_package = Element("package", {"name": folderPath.replace("/", "."),
                                              "_path": folderPath,
                                              "line-rate": getLinesRate(item),
                                              "branch-rate": getBranchRate(item),
                                              "complexity": computeComplexity(item)
                                          })
            classes = SubElement(new_package, "classes")
            traverseCovXML(item, parentElement=classes, packages=packages, package=new_package)
            if len(classes):
                for attr_key, attr_value in new_package.items():
                    if attr_key.startswith("_"):
                        del new_package.attrib[attr_key]
                packages.append(new_package)
        elif getTagName(item) == "src":
            clazz = SubElement(parentElement, "class",
                               {"name": f"{package.get('name')}.{item.get('name').replace('.', '-')}",
                                "line-rate": getLinesRate(item),
                                "branch-rate": getBranchRate(item),
                                "complexity": computeComplexity(item),
                                "filename": f"{package.get('_path')}/{item.get('name')}"
                                })
            lines = SubElement(clazz, "lines")
            for fnElem in item:
                for elem in fnElem:
                    lineNum = elem.get("line")
                    if not lineNum:
                        continue
                    if getTagName(elem) == "probe" and elem.get("kind") == "decision":
                        line = SubElement(lines, "line",
                                          {"number": lineNum,
                                           "hits": "0" if elem.get("event", "none") == "none" else "1",
                                           "branch": "true",
                                           "condition-coverage": bullseyeEventToCobertura(elem.get("event"))
                                           })
                        conditions = SubElement(line, "conditions")
                        SubElement(conditions, "condition", {"number": lineNum,
                                                             "type": "switch" if elem.get("kind") == "switch-label" else "jump",
                                                             "coverage": bullseyeEventToCobertura(elem.get("event"))})
                    elif getTagName(elem) == "block":
                        SubElement(lines, "line",
                                   {"number": lineNum,
                                    "hits": elem.get("entered", "0"),
                                    "branch": "false"})


def convertToCobertura(covXML: str, outputPath: str, sources: Optional[List[str]] = None):
    """
    Folder -> package
    Src -> class
    Fn -> lines, line (flattened)
    Note: methods/method are skipped in the resulting cobertura.xml, not all parsers understand and consider them.
    For example in AzureDevOps those are not recognized.
    """
    # https://www.bullseye.com/help/ref-covxml.html
    with open(covXML) as f:
        tree = ElementTree.parse(f)
    root = tree.getroot()

    coverage = Element('coverage', {"line-rate": getLinesRate(root),
                                    "branch-rate": getBranchRate(root),
                                    "lines-covered": root.get("cd_cov", "0"),
                                    "lines-valid": root.get("cd_total", "0"),
                                    "branches-covered": root.get("d_cov", "0"),
                                    "branches-valid": root.get("d_total", "0")})
    if sources:
        sourcesElement = SubElement(coverage, "sources")
        for source in sources:
            sourceElement = SubElement(sourcesElement, "source")
            sourceElement.text = source

    packages = SubElement(coverage, "packages")

    traverseCovXML(root, parentElement=packages, packages=packages)

    # serialize to xml file
    dom = minidom.parseString(ElementTree.tostring(coverage, encoding="utf8", method="xml"))
    with open(outputPath, "w", encoding="utf8") as f:
        f.write(dom.toprettyxml(indent="  "))


def main(args):
    if len(args) < 2:
        print(f"Usage: ./{sys.argv[0]} <covXML path> <output path>")
        return
    covXML = args[0]
    outputPath = args[1]
    sources = []
    if len(args) > 2:
        sources = args[2].split(",")

    convertToCobertura(covXML, outputPath, sources)


if __name__ == '__main__':
    main(sys.argv[1:])
