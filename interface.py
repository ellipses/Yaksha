#!/usr/bin/python
from commands import ifgc, voting, actions
from commands import utilities


class Interface():

    def __init__(self):
        self._func_mapping = {}
        self._class_mapping = {}
        self._modules = [ifgc, voting, actions]
        self.remap_functions()

    def remap_functions(self):
        '''
        We replace value for each dictionary key from containing
        a function name to a tuple containing a reference to the
        function and a the name of the class it belongs to. The
        class name is used to select the correct class from the
        class_mapping dictionary. 
        '''
        import pdb;pdb.set_trace()
        name_mapping = utilities.get_callbacks()

        for key, value in name_mapping.items():
            class_name, func_name = value[0].split('.')
            module_name = value[1]
            # Go through the imported modules to determine which
            # module the class belongs to.
            for module in self._modules:
                if module.__name__ != module_name:
                    continue
                else:
                    class_ref = getattr(module, class_name)
                    func_ref = getattr(class_ref, func_name)

                    # Check if we already have a reference to
                    # this class and add it if not.
                    if class_name in self._class_mapping:
                        self._class_mapping[class_name] = class_ref

                    # Replace the function name with a tuple
                    # containing a reference to the function and
                    # the class name. The class name will be used
                    # get the correct class from self._class_mapping.
                    self._func_mapping[key] = (func_ref, class_name)

                    # We found the module so there is no need for further
                    # iterations.
                    break

            # Go through the class mapping and replace references to the class's
            # with their instances.
            for key, value in self._class_mapping.items():
                self._class_mapping[key] = value()

    async def call_command(self, command, *args, **kwargs):
        '''
        Determines which function to call from the func_mapping
        dict using the command arg as the key.
        '''
        func, class_name = self._func_mapping[command]
        # Call the actual function passing the instance of the
        # class as the first argument. 
        await func(self._class_mapping[class_name], *args, **kwargs)


interface = Interface()