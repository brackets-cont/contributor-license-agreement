def _seek_next_session(start_line, diff):
    i = start_line
    while( i < len(diff)):
            line = diff[i]
            if line.startswith('@@'):
                return i
            i += 1
    return i

def _get_all_changes_in_session(start_line, diff, diff_details):
    i = start_line
    while( i < len(diff)):
            line = diff[i]
            if line.startswith('+'):
                diff_details['linesAdded'].append(line)
            if line.startswith('-'):
                diff_details['linesRemoved'].append(line)
            if line.startswith(' '):
                diff_details['linesUnchanged'].append(line)
            if line.startswith('diff'): # Next session start
                return i
            i += 1
    return i


def get_diff_details(diffString):
    diff = diffString.splitlines()
    diff_details = {
        'linesRemoved' : [],
        'linesAdded': [],
        'linesUnchanged': []
    }
    
    i = 0
    while i < len(diff):
        # seek session start @@
        i = _seek_next_session(i, diff)
        i = _get_all_changes_in_session(i,diff,diff_details)
    
    print(diff_details['linesRemoved'])
    return diff_details
