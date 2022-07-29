class GroupManager:

    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value

    def __add_group(self, group_name, value):
        uppercased_group_name = group_name.upper()
        if hasattr(self, uppercased_group_name):
            raise ValueError(f'Group name {group_name} already used')
        setattr(self, uppercased_group_name, value)

    def add_left_group(self, group_name):
        if self.min_value > -1:
            raise ValueError('Left groups exhausted, decrease min value')
        self.__add_group(group_name, self.min_value)
        self.min_value += 1

    def add_right_group(self, group_name):
        if self.max_value < 1:
            raise ValueError('Right groups exhausted, increase max value')
        self.__add_group(group_name, self.max_value)
        self.max_value -= 1

group_manager = GroupManager(-1000, 1000)

group_manager.add_left_group('load_user')
group_manager.add_right_group('save_user')
