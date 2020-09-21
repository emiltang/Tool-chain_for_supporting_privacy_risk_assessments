from Templates.ITemplate import ITransformation, IPrivacyAttack
import Templates
from importlib import import_module
import inspect, sys
from rdflib import Graph, Namespace, URIRef, Literal, exceptions
import rdflib
import rdflib.plugin
from rdflib.compare import to_isomorphic, graph_diff, to_canonical_graph
import json
from Framework.Data import Data
from Framework.Templates.transforamtion import Util as TransformationUtil
from Framework.Templates.privacyAttack import Util as PrivacyAttackUtil
from Framework.Risk.Analysis import Analysis
from Framework.Risk.visualize import Visualize_full
import time
import importlib
from Framework.Templates.validator import Privacy_attack_validator, Transforamtion_validator, Input_validator

class Driver:
    def __init__(self, domain_path="./Ontologies/smartbuildingprivacyvunl.ttl", base_ontology_path=None, extention_ontology_path=None, domain_NS = Namespace('https://ontology.hviidnet.com/2020/01/03/smartbuildingprivacyvunl.ttl#'), debug_mode=False):
        self.domain_path = domain_path
        self.base_ontology_path = base_ontology_path if base_ontology_path is not None else "./Ontologies/privacyvunl.ttl"
        self.extention_ontology_path = extention_ontology_path if extention_ontology_path is not None else "./Ontologies/privacyvunlv2.ttl"
        self.transformationUtil = TransformationUtil(self.domain_path,self.base_ontology_path,self.extention_ontology_path)
        self.privacyAttackUtil = PrivacyAttackUtil(self.domain_path,self.base_ontology_path,self.extention_ontology_path)
        self.analyses = Analysis(self.domain_path,self.base_ontology_path,self.extention_ontology_path)
        self.domain_NS = domain_NS
        self.debug_mode = debug_mode

    def run(self,inputModel, nameing_of_output = None):
        input_validator = Input_validator(self.domain_path,self.base_ontology_path,self.extention_ontology_path)

        if not input_validator.validate(inputModel):
            return inputModel

        inputModel = self._use_templates(inputModel, nameing_of_output)
        risk_results = self.analyses.find_privacy_scores(inputModel, nameing_of_output)
        self.generated_visualization(inputModel, nameing_of_output)
        return inputModel

    def _use_templates(self,inputModel, nameing_of_output = None):
        seconds = time.time()

        print("Using Transformations")
        inputModel = self._use_transformations(inputModel)
        if self.debug_mode:
            print("Transformations time in seconds:", time.time()- seconds)
            seconds = time.time()
            inputModel.serialize("transforamtion_graph.rdf")

        print("Using Privacy Attacks")
        inputModel = self._use_privacy_attacks(inputModel)
        if self.debug_mode:
            print("Privacy Attacks time in seconds:", time.time()- seconds)

        if nameing_of_output is not None:
            inputModel.serialize(nameing_of_output + ".rdf")
        if self.debug_mode:
            inputModel.serialize("full_graph.rdf")
        return inputModel

    def generated_visualization(self,input_model, nameing_of_output=None):
        print("Generated Visualization")
        visualize = Visualize_full(input_model, self.base_ontology_path, self.extention_ontology_path, self.domain_path)
        visualize.generated_visualization(nameing_of_output)

    def _use_transformations(self, inputModel):
        classes_potential_transformations = self._find_all_transformations()
        potential_transformations = []
        validator = Transforamtion_validator(self.domain_path, self.base_ontology_path, self.extention_ontology_path)

        for transformation_class in classes_potential_transformations:
            temp_class = transformation_class()
            model = temp_class.get_model()
            if validator.validate(model, str(temp_class.__class__)):
                potential_transformations.append(temp_class)
        amount_of_triples = len(inputModel)
        counter = 1
        used_all_transforamtions = False
        while not used_all_transforamtions :
            for potential_transformation in potential_transformations:
                inputModel = self._combind_graph(inputModel, potential_transformation.get_model())
            if amount_of_triples < len(inputModel):
                amount_of_triples = len(inputModel)
            else:
                used_all_transforamtions = True
            if self.debug_mode:
                print("Done with " + str(counter) + " genurations for transformations")
            counter += 1
        return inputModel

    def _use_privacy_attacks(self, inputModel):
        classes_potential_privacy_attacks = self._find_all_privacy_attacks()
        potential_privacy_attacks = []
        validator = Privacy_attack_validator(self.domain_path, self.base_ontology_path, self.extention_ontology_path)
        for privacy_attacks_class in classes_potential_privacy_attacks:
            temp_class = privacy_attacks_class()
            model = temp_class.get_model()
            if validator.validate(model, str(temp_class.__class__)):
                potential_privacy_attacks.append(temp_class)

        for potential_privacy_attack in potential_privacy_attacks:
            inputModel = self._combind_graph(inputModel, potential_privacy_attack.get_model())

        return inputModel

    def _combind_graph(self,inputModel,template):
        templateUtil = None
        templateName = ""

        valied_transformation = self.transformationUtil.validate_template(template)
        valied_privacy_attack = self.privacyAttackUtil.validate_template(template)

        if valied_transformation is not None and valied_privacy_attack is not None:
            print("Template most have either a transforamtion or a privacy attfind_time_resolution_for_transformatione")
        elif valied_transformation is not None and valied_privacy_attack is not None and valied_transformation ^ valied_privacy_attack:
            print("Template may only have a transformation or privacy attack")
            return inputModel

        if valied_transformation:
            templateUtil = self.transformationUtil
            # templateName = templateUtil.get_template_name(template)
        elif valied_privacy_attack:
            templateUtil = self.privacyAttackUtil
        else:
            return inputModel

            # templateName = templateUtil.get_template_name(template)

        seconds = time.time()

        context_used_data_inputs =  templateUtil.can_template_be_used(inputModel, template)
        for context in context_used_data_inputs.keys():
            #use the template to extend the input model.
            inputModel = templateUtil.combind_using_template(inputModel,template, context_used_data_inputs[context], context=context)
        return inputModel

    def _find_all_transformations(self):
        loaded_modules = []
        domain_folder_name = self.domain_NS.split("/")
        domain_folder_name = domain_folder_name[len(domain_folder_name)-1].split(".")
        domain_folder_name = domain_folder_name[0]
        model_name = "Templates."+domain_folder_name+".Transformations"
        my_module = importlib.import_module(model_name)
        for module in my_module.__all__:
            loaded_modules.append(import_module(model_name + "."+ module))

        transformation_classes = []
        for module in loaded_modules:
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj):
                    if  model_name + "." in str(obj):
                        if issubclass(obj, ITransformation):
                            if obj.__DOMAINNAMESPACE__ == self.domain_NS:
                                transformation_classes.append(obj)
        return transformation_classes

    def _find_all_privacy_attacks(self):
        loaded_modules = []
        domain_folder_name = self.domain_NS.split("/")
        domain_folder_name = domain_folder_name[len(domain_folder_name)-1].split(".")
        domain_folder_name = domain_folder_name[0]
        model_name = "Templates."+domain_folder_name+".PrivacyAttacks"
        my_module = importlib.import_module(model_name)
        for module in my_module.__all__:
            loaded_modules.append(import_module(model_name + "."+ module))

        privacy_attacks_classes = []
        for module in loaded_modules:
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj):
                    if  model_name + "." in str(obj):
                        if issubclass(obj, IPrivacyAttack):
                            if obj.__DOMAINNAMESPACE__ == self.domain_NS:
                                privacy_attacks_classes.append(obj)
        return privacy_attacks_classes
