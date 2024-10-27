import json

with open("C:/Users/Marius/Downloads/testcase.json") as f:
    data = json.load(f)

actual_data_as_json_string = data["parameters"]["parameters/body"]

with open("C:/Users/Marius/Downloads/testcase-extracted.json", "wt") as f:
    f.write(actual_data_as_json_string)

