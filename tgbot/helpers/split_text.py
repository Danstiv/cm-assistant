SPLIT_ERROR = 'Text cannot be split with the given parameters'


def split_text(header, body, max_part_length, unit='char', header_separator='\n', include_part_numbers=True):
    if len(header) + len(header_separator) + len(body)<=max_part_length:
        return [(header+header_separator if header else '')+body]
    if unit == 'char':
        units = list(body)
        unit_separator = None
    if unit == 'word':
        units = body.split(' ')
        unit_separator = ' '
    if unit == 'line':
        units = body.split('\n')
        unit_separator = '\n'
    total_parts = 0
    fixed_part_length = len(header)
    if fixed_part_length > 0:
        fixed_part_length += 4 + len(header_separator)
    else:
        fixed_part_length += 1 + len(header_separator)
    current_part = 1
    temp_units = list(units)
    recalculation_required = False
    if include_part_numbers:
        while True:
            part_header_length = fixed_part_length+len(str(current_part))
            if current_part <= total_parts:
                part_header_length += len(str(total_parts))
            else:
                part_header_length += len(str(total_parts+1))
            if part_header_length >= max_part_length and temp_units:
                raise ValueError(SPLIT_ERROR)
            free_chars = max_part_length - part_header_length
            if unit == 'char':
                part_length = len(temp_units[:free_chars])
                del temp_units[:free_chars]
            else:
                part_length = 0
                for u in list(temp_units):
                    if len(u)>free_chars:
                        raise ValueError(SPLIT_ERROR)
                    temp = 0
                    if part_length:
                        temp = len(unit_separator)
                    temp += len(u)
                    if part_length + temp > free_chars:
                        break
                    part_length += temp
                    temp_units.remove(u)
            if not part_length:
                if not recalculation_required:
                    break
                current_part = 1
                temp_units = list(units)
                recalculation_required = False
                continue
            if current_part > total_parts:
                total_parts += 1
                recalculation_required = True
            current_part += 1
    messages = []
    while True:
        if include_part_numbers:
            if header:
                message = f'{header} ({len(messages)+1}/{total_parts}){header_separator}'
            else:
                message = f'{len(messages)+1}/{total_parts}{header_separator}'
        else:
            if header:
                message = f'{header}{header_separator}'
            else:
                message = ''
        if unit == 'char':
            message_length = len(message)
            message += ''.join(units[:max_part_length-message_length])
            del units[:max_part_length-message_length]
        else:
            added = False
            for u in list(units):
                temp = ''
                if added:
                    temp = unit_separator
                temp += u
                if len(message) + len(temp) > max_part_length:
                    break
                message += temp
                added = True
                units.remove(u)
        messages.append(message)
        if not units:
            break
    return messages


def split_text_by_units(header, body, max_part_length, units=['line', 'word', 'char'], header_separator='\n', include_part_numbers=True):
    for unit in units:
        try:
            return split_text(header, body, max_part_length, unit, header_separator, include_part_numbers)
        except ValueError:
            pass
    raise ValueError(SPLIT_ERROR)
