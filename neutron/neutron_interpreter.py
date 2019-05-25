import neutron_lexer, neutron_parser
import pprint
import errors
from os import path
import sly
import pysnooper
from numpy import array

global global_objects, global_class_templates, paths_to_look_in
global_objects, global_class_templates = {}, {}
paths_to_look_in = [path.abspath(__file__)]

class Process:
    def __init__(self, tree, filename="?"):
        self.tree = tree
        self.objects = {}
        self.class_templates = {}
        self.type = "PROGRAM"
        self.file_path = filename
        self.stmt = {
            "FUNCTION_DECLARATION": self.function_declaration,
            "VARIABLE_ASSIGNMENT": self.assign_variable,
            "FUNCTION_CALL": self.object_call,
            "PYTHON_CODE": self.python_code,
            "CLASS_DECLARATION": self.class_declaration,
            "GET": self.get_stmt,
            "CONDITIONAL": self.conditional,
        }

    def in_program(self):
        return True if self.type == "PROGRAM" else False

    def run(self, tree = None):
        if tree == None:
            for line in self.tree:
                self.stmt[line[0]](line[1:])
        elif tree != None:
            for line in tree:
                self.stmt[line[0]](line[1:])

    def eval_int(self, tree):
        value = IntType(tree)
        return value

    def eval_float(self, tree):
        value = FloatType(tree)
        return value

    def eval_string(self, tree):
        value = StringType(tree)
        return value

    def eval_id(self, tree):
        name = tree[0]["VALUE"]
        if name in global_objects:
            value = global_objects[name]
        elif name in self.objects:
            value = self.objects[name]
        else:
            errors.variable_referenced_before_assignment_error().raise_error(f"variable \"{name}\" referenced before assignment")

        return value

    def class_declaration(self, tree):
        dictionary = tree[0]
        name = dictionary["ID"]
        program = dictionary["PROGRAM"]
        if self.in_program():
            global_class_templates[name] = ClassTemplate(program, name)
        elif not self.in_program():
            self.class_templates[name] = ClassTemplate(program, name)

    def class_attribute(self, body):
        if self.type == "FUNCTION" and body["CLASS"] == "this":
            if isinstance(self.objects["this"], ClassTemplate):
                value = self.objects["this"].objects[body["ATTRIBUTE"]]
            else:
                try:
                    value = self.objects["this"].objects[body["ATTRIBUTE"]]
                except KeyError:
                    errors.variable_referenced_before_assignment_error().raise_error(f"variable \"{name}\" referenced before assignment")

        else:
            classes = {**self.objects, **global_objects}
            value = classes[body["CLASS"]].objects[body["ATTRIBUTE"]]

        return value

    ### Don't Mind The Spaghetti Code Subject to Change ###
    def conditional(self, tree):
        dictionary = tree[0]
        _if = dictionary["IF"][1]
        _elsif = dictionary["ELSE_IF"][1]
        _else = dictionary["ELSE"][1]
        if _if != None and _elsif == None and _else == None:
            if self.eval_expression(_if["CONDITION"]) == True:
                self.run(tree=_if["CODE"])
        if _if != None and _elsif == None and _else != None:
            if self.eval_expression(_if["CONDITION"]) == True:
                self.run(tree=_if["CODE"])
            else:
                self.run(tree=_else["CODE"])
        if _if != None and _elsif != None and _else == None:
            if self.eval_expression(_if["CONDITION"]) == True:
                self.run(tree=_if["CODE"])
            for stmt in _elsif:
                if self.eval_expression(stmt["CONDITION"]) == True:
                    self.run(stmt["CODE"])
        if _if != None and _elsif != None and _else != None:
            if self.eval_expression(_if["CONDITION"]) == True:
                self.run(tree=_if["CODE"])
                return
            for stmt in _elsif:
                if self.eval_expression(stmt["CONDITION"]) == True:
                    self.run(stmt["CODE"])
                    return
            self.run(tree=_else["CODE"])

    def eval_sub(self, tree):
        return self.eval_expression(tree[0]) - self.eval_expression(tree[1])
    def eval_add(self, tree):
        return self.eval_expression(tree[0]) + self.eval_expression(tree[1])
    def eval_mul(self, tree):
        return self.eval_expression(tree[0]) * self.eval_expression(tree[1])
    def eval_div(self, tree):
        return self.eval_expression(tree[0]) / self.eval_expression(tree[1])
    def eval_mod(self, tree):
        return self.eval_expression(tree[0]) % self.eval_expression(tree[1])

    def eval_neg(self, tree):
        return -self.eval_expression(tree)
    def eval_pos(self, tree):
        return +self.eval_expression(tree)

    def eval_bool(self, tree):
        val = tree["VALUE"]
        return True if val == "true" else False
    def eval_eqeq(self, tree):
        return self.eval_expression(tree[0]) == self.eval_expression(tree[1])
    def eval_not_eqeq(self, tree):
        return self.eval_expression(tree[0]) != self.eval_expression(tree[1])
    def eval_eq_greater(self, tree):
        return self.eval_expression(tree[0]) >= self.eval_expression(tree[1])
    def eval_eq_less(self, tree):
        return self.eval_expression(tree[0]) <= self.eval_expression(tree[1])
    def eval_less(self, tree):
        return self.eval_expression(tree[0]) < self.eval_expression(tree[1])
    def eval_greater(self, tree):
        return self.eval_expression(tree[0]) > self.eval_expression(tree[1])

    def eval_and(self, tree):
        if self.eval_expression(tree[0]) == True:
            if self.eval_expression(tree[1]) == True:
                return True
        else:
            return False
    def eval_or(self, tree):
        if self.eval_expression(tree[0]) == True:
            return True
        elif self.eval_expression(tree[1]) == True:
            return True
        else:
            return False
    def eval_not(self, tree):
        return False if self.eval_expression(tree) == True else True

    def eval_numpy(self, tree):
        return NumpyArray(tree, scope=self)
    def eval_list(self, tree):
        return ListType(tree, scope=self)
    def eval_tuple(self, tree):
        return TupleType(tree, scope=self)

    def eval_expression(self, tree):
        _type = tree[0]
        body = tree[1:]
        value = None

        type_to_function = {
            # Data Types
            "INT": self.eval_int,
            "FLOAT": self.eval_float,
            "BOOl": self.eval_bool,
            "STRING": self.eval_string,
            "ID": self.eval_id,
            "NUMPY": self.eval_numpy,
            "LIST": self.eval_list,
            "TUPLE": self.eval_tuple,

            # Bin Ops
            "SUB": self.eval_sub,
            "ADD": self.eval_add,
            "MUL": self.eval_mul,
            "DIV": self.eval_div,
            "MOD": self.eval_mod,
            "NEG": self.eval_neg,
            "POS": self.eval_pos,

            # Bool Ops
            "EQEQ": self.eval_eqeq,
            "NOT_EQEQ": self.eval_not_eqeq,
            "EQ_LESS": self.eval_eq_less,
            "EQ_GREATER": self.eval_eq_greater,
            "OR": self.eval_or,
            "NOT": self.eval_not,
            "AND": self.eval_and,
            "GREATER": self.eval_greater,
            "LESS": self.eval_less,

            # Functionality
            "FUNCTION_CALL": self.object_call,
            "CLASS_ATTRIBUTE": self.class_attribute
        }

        if _type in type_to_function:
            value = type_to_function[_type](body)
        elif type == "PYTHON_CODE":
            value = self.python_code((body, ), eval_or_not=True)

        return value

    ### End of Spaghetti Code *relief* ###

    def python_code(self, tree, eval_or_not=False):
        code = tree[0]["CODE"]
        if eval_or_not:
            return eval(code)
        elif not eval_or_not:
            exec(code)

    def assign_variable(self, tree):
        dictionary = tree[0]
        value = self.eval_expression(dictionary["EXPRESSION"])
        if not isinstance(value, Function):
            self.objects[dictionary["ID"]] = value
        elif isinstance(value, Function):
            self.objects[dictionary["ID"]] = value

    def get_variable(self, name):
        if name in global_objects:
            return global_objects[name]
        elif name in self.objects:
            return self.objects[name]
        else:
            errors.variable_referenced_before_assignment_error().raise_error(f"variable \"{name}\" referenced before assignment")


    def object_call(self, tree):
        dictionary_func = tree[0]
        dictionary = dictionary_func["FUNCTION_ARGUMENTS"]
        new_pos_arguments = []
        class_template = {**self.class_templates, **global_class_templates}
        objects = {**self.objects, **global_objects}

        if "POSITIONAL_ARGS" in dictionary:
            for expr in dictionary["POSITIONAL_ARGS"]:
                new_pos_arguments.append(self.eval_expression(expr))

        elif "POSITIONAL_ARGS" not in dictionary:
            dictionary["POSITIONAL_ARGS"] = (None, )
        if "KWARGS" not in dictionary:
            dictionary["KWARGS"] = (None, )

        if dictionary_func["ID"][0] == "ID":
            name = dictionary_func["ID"][1]["VALUE"]
            if name in class_template:
                return_value = ClassInstance(class_template[name], None, new_pos_arguments, dictionary["KWARGS"])
            elif name not in objects and name not in class_template:
                errors.variable_referenced_before_assignment_error().raise_error(f"variable \"{name}\" referenced before assignment")
            elif isinstance(objects[name], Function):
                return_value = objects[name].run_function(new_pos_arguments, dictionary["KWARGS"])
            else:
                try:
                    return_value = objects[name].run_function(new_pos_arguments, dictionary["KWARGS"])
                except AttributeError:
                    errors.id_not_callable().raise_error(f"object \"{name}\" not callable")

        elif dictionary_func["ID"][0] == "CLASS_ATTRIBUTE":
            if self.type == "PROGRAM":
                classes = {**self.objects, **global_objects}
                attribute = dictionary_func["ID"][1]["ATTRIBUTE"]
                class_name = dictionary_func["ID"][1]["CLASS"]
                return_value = objects[class_name].run_method(attribute, dictionary_func["FUNCTION_ARGUMENTS"]["POSITIONAL_ARGS"], dictionary_func["FUNCTION_ARGUMENTS"]["KWARGS"])
            elif self.type == "FUNCTION":
                if isinstance(self.positional_arguments[0], ClassTemplate) and dictionary_func["ID"][1]["CLASS"] == "this":
                    classes = {"this": self.positional_arguments[0]}
                    attribute = dictionary_func["ID"][1]["ATTRIBUTE"]
                    class_name = dictionary_func["ID"][1]["CLASS"]
                    return_value = objects[class_name].run_method(attribute, dictionary_func["FUNCTION_ARGUMENTS"]["POSITIONAL_ARGS"], dictionary_func["FUNCTION_ARGUMENTS"]["KWARGS"])

        elif dictionary_func["ID"][0] != "ID":
            object_not_callable = errors.ErrorClass(f"{dictionary_func['ID'][0].lower()}_not_callable_error")
            object_not_callable.raise_error(f"{dictionary_func['ID'][0].lower()} type is not callable")

        return return_value

    def get_stmt(self, tree):
        dictionary = tree[0]
        for path in paths_to_look_in:
            pass


    def function_declaration(self, tree):
        dictionary = tree[0]
        name = dictionary["ID"]
        arguments = dictionary["FUNCTION_ARGUMENTS"]
        program = dictionary["PROGRAM"]
        if self.in_program():
            global_objects[name] = Function(program, name, arguments)
        elif not self.in_program():
            self.objects[name] = Function(program, name, arguments)


class Function(Process):
    def __init__(self, tree, name, arguments):
        Process.__init__(self, tree)
        self.name = name
        self.type = "FUNCTION"
        self.arguments = arguments
        self.tree = tree
        self.stmt = {**self.stmt, "CLASS_ATTRIBUTE_ASSIGNMENT": self.attribute_assignment}
        self.evaluate_arguments()

    def evaluate_arguments(self):
        self.positional_arguments = []
        self.kw_arguments = {}
        for key in self.arguments:
            if key == "POSITIONAL_ARGS":
                for item in self.arguments[key]:
                    self.positional_arguments.append(item[1]["VALUE"])
            if key == "KWARGS":
                for item in self.arguments[key]:
                    self.kw_arguments[item["ID"]] = self.eval_expression(item["EXPRESSION"])

    def run_function(self, pos_arguments, kw_args):
        kw_arguments = {}
        if len(pos_arguments) != len(self.positional_arguments):
            errors.positional_argument_error.raise_error(self, f"{len(self.positional_arguments)} arguments expected {len(pos_arguments)} were found")

        for i, name in enumerate(self.positional_arguments):
            self.objects[name] = pos_arguments[i]

        try:
            for item in kw_args:
                    kw_arguments[item["ID"]] = item["EXPRESSION"]

            for variable in self.kw_arguments:
                if variable not in kw_args:
                    self.objects[variable] = self.kw_arguments[variable]
                elif variable in kw_args:
                    self.objects[variable] = kw_arguments["ID"]

        except TypeError:
            pass

        self.run()
        if "--return--" in self.objects:
            return self.objects["--return--"]
        elif "--return--" not in self.objects:
            return None

    def attribute_assignment(self, tree):
        dictionary = tree[0]
        if "this" in self.objects and isinstance(self.objects["this"], ClassTemplate):
            if dictionary["CLASS_ATTRIBUTE"][1]["CLASS"] == "this":
                attribute = dictionary["CLASS_ATTRIBUTE"][1]["ATTRIBUTE"]
            else:
                errors.variable_referenced_before_assignment_error().raise_error(f"\"{dictionary['CLASS_ATTRIBUTE'][1]['CLASS']}\" class attributes cannot be changed. Consider making a setter method in the class")

        else:
            errors.type_error().raise_error("\"this\" object is not defined or is not a class")

        self.objects["this"].objects[attribute] = self.eval_expression(dictionary["EXPRESSION"])


class ClassTemplate(Function):
    def __init__(self, tree, name):
        Process.__init__(self, tree)
        self.stmt = {
            "FUNCTION_DECLARATION": self.function_declaration,
        }
        self.name = name
        self.type = "CLASS_TEMPLATE"
        self.run()

        if "--init--" in self.objects:
            self.positional_arguments = self.objects["--init--"].positional_arguments
            self.kw_arguments = self.objects["--init--"].kw_arguments
        else:
            self.positional_arguments, self.kw_arguments = None, None

    def run_method(self, name_func, pos_arguments, kw_arguments):
        objects = {**self.objects, **global_objects}
        return objects[name_func].run_function([self, ] + list(pos_arguments), kw_arguments)


class ClassInstance(ClassTemplate):
    def __init__(self, instance, name, pos_arguments, kw_arguments):
        ClassTemplate.__init__(self, instance.tree, instance.name)
        self.name = name
        self.type = "CLASS_INSTANCE"
        self.run_method("--init--", pos_arguments, kw_arguments)


class DataType:
    def __init__(self, tree, scope=None):
        self.tree = tree
        self.scope = scope
        self.value = self.eval_tree()

    def eval_tree(self):
        return None

    def __repr__(self):
        return f"neutron::{self.__class__.__name__} <value: {self.value}>"
    def __add__(self, other):
        return self.value + other.value
    def __mul__(self, other):
        print(self.value, other.value)
        return self.value * other.value
    def __sub__(self, other):
        return self.value - other.value
    def __truediv__(self, other):
        return self.value / other.value
    def __mod__(self, other):
        return self.value % other.value
    def __str__(self):
        return self.value


class IntType(DataType):
    def eval_tree(self):
        return int(self.tree[0]["VALUE"])


class FloatType(DataType):
    def eval_tree(self):
        return float(self.tree[0]["VALUE"])


class NumpyArray(DataType):
    def eval_tree(self):
        tree = self.tree[0]["ITEMS"]
        value = []
        for item in tree:
            value.append(self.scope.eval_expression(item))
        return array(value)
    def __str__(self):
        return f"({self.value.__str__()[1:-1]})"


class ListType(DataType):
    def eval_tree(self):
        tree = self.tree[0]["ITEMS"]
        value = []
        for item in tree:
            value.append(self.scope.eval_expression(item))
        return list(value)
    def __str__(self):
        return self.value.__str__()

class TupleType(DataType):
    def eval_tree(self):
        tree = self.tree[0]["ITEMS"]
        value = ()
        for item in tree:
            value += (item, )
        return tuple(value)
    def __str__(self):
        return self.value.__str__()


class StringType(DataType):
    def eval_tree(self):
        return str(self.tree[0]["VALUE"])



## Tests
"""if __name__ == '__main__':
pp = pprint.PrettyPrinter(indent=2)
text = """
"""
get("io/console");
print("hi");
"""
"""

lexer = neutron_lexer.NeutronLexer()
parser = neutron_parser.NeutronParser()
# for tok in lexer.tokenize(text_test + text):
#    print(tok)
tree = parser.parse(lexer.tokenize(text_test + text))
pp.pprint(tree)
program = Process(tree)
program.run()text_test"""