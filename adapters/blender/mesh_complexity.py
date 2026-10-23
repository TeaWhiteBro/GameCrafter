"""Count expanded instances while visiting each shared mesh only once per call."""

def triangle_count(objects):
    counts = {}
    total = 0
    for obj in objects:
        mesh = obj.data
        key = mesh.as_pointer()
        if key not in counts:
            counts[key] = sum(len(face.vertices) - 2 for face in mesh.polygons)
        total += counts[key]
    return total
