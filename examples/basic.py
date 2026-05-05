from uniqdiff import compare

result = compare([1, 2, 3], [3, 4, 5], include_common=True)

print(result.to_dict())
