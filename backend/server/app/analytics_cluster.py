from __future__ import annotations

import random


def run_kmeans(
    vectors: list[list[float]],
    cluster_count: int,
    max_iter: int = 100,
    tolerance: float = 1e-4,
    restarts: int = 8,
    random_seed: int = 42,
) -> tuple[list[int], list[list[float]]]:
    if not vectors:
        return [], []
    if cluster_count <= 0:
        raise ValueError("cluster_count must be positive")

    effective_clusters = min(cluster_count, len(vectors))
    scaled_vectors = _standardize(vectors)

    best_assignments: list[int] | None = None
    best_inertia: float | None = None
    rng = random.Random(random_seed)

    for restart in range(restarts):
        centers = _initialize_kmeans_pp(scaled_vectors, effective_clusters, rng.randint(0, 10_000) + restart)
        assignments = [0] * len(scaled_vectors)

        for _ in range(max_iter):
            next_assignments = [
                min(
                    range(effective_clusters),
                    key=lambda cluster_id: _distance_list(vector, centers[cluster_id]),
                )
                for vector in scaled_vectors
            ]

            next_centers = []
            for cluster_id in range(effective_clusters):
                cluster_vectors = [
                    vector
                    for vector, assignment in zip(scaled_vectors, next_assignments)
                    if assignment == cluster_id
                ]
                if not cluster_vectors:
                    farthest_index = _farthest_vector_index(scaled_vectors, centers)
                    next_centers.append(scaled_vectors[farthest_index][:])
                    continue
                next_centers.append([
                    _avg([vector[feature_index] for vector in cluster_vectors])
                    for feature_index in range(len(cluster_vectors[0]))
                ])

            center_shift = max(
                _distance_list(old_center, new_center)
                for old_center, new_center in zip(centers, next_centers)
            )
            centers = next_centers
            assignments = next_assignments
            if center_shift <= tolerance:
                break

        inertia = sum(
            _distance_sq(vector, centers[assignment])
            for vector, assignment in zip(scaled_vectors, assignments)
        )
        if best_inertia is None or inertia < best_inertia:
            best_inertia = inertia
            best_assignments = assignments[:]

    assert best_assignments is not None
    original_centers = []
    for cluster_id in range(effective_clusters):
        cluster_vectors = [
            vector
            for vector, assignment in zip(vectors, best_assignments)
            if assignment == cluster_id
        ]
        if not cluster_vectors:
            original_centers.append(vectors[0][:])
            continue
        original_centers.append([
            _avg([vector[feature_index] for vector in cluster_vectors])
            for feature_index in range(len(cluster_vectors[0]))
        ])

    return best_assignments, original_centers


def _initialize_kmeans_pp(vectors: list[list[float]], cluster_count: int, seed: int) -> list[list[float]]:
    rng = random.Random(seed)
    centers = [vectors[rng.randrange(len(vectors))][:]]
    while len(centers) < cluster_count:
        distances = [
            min(_distance_sq(vector, center) for center in centers)
            for vector in vectors
        ]
        total_distance = sum(distances)
        if total_distance <= 0:
            candidate = vectors[rng.randrange(len(vectors))][:]
            centers.append(candidate)
            continue
        threshold = rng.random() * total_distance
        cumulative = 0.0
        for vector, distance in zip(vectors, distances):
            cumulative += distance
            if cumulative >= threshold:
                centers.append(vector[:])
                break
    return centers


def _standardize(vectors: list[list[float]]) -> list[list[float]]:
    means = [
        _avg([vector[index] for vector in vectors])
        for index in range(len(vectors[0]))
    ]
    stds = []
    for index in range(len(vectors[0])):
        variance = _avg([
            (vector[index] - means[index]) ** 2
            for vector in vectors
        ])
        stds.append(variance ** 0.5)
    return [
        [
            (value - means[index]) / (stds[index] if stds[index] > 1e-8 else 1.0)
            for index, value in enumerate(vector)
        ]
        for vector in vectors
    ]


def _farthest_vector_index(vectors: list[list[float]], centers: list[list[float]]) -> int:
    best_index = 0
    best_distance = -1.0
    for index, vector in enumerate(vectors):
        nearest = min(_distance_sq(vector, center) for center in centers)
        if nearest > best_distance:
            best_index = index
            best_distance = nearest
    return best_index


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _distance_sq(left: list[float], right: list[float]) -> float:
    return sum((lhs - rhs) ** 2 for lhs, rhs in zip(left, right))


def _distance_list(left: list[float], right: list[float]) -> float:
    return _distance_sq(left, right) ** 0.5
