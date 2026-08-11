from la_caja import SuperIndex


def test_identical_profile_reuses_node_and_reinforces_it():
    index = SuperIndex()
    first = index.register({"tree": 1.0, "bird": 0.8})
    second = index.register({"bird": 0.8, "tree": 1.0})

    assert first is second
    assert first.relevance_weight == 2


def test_lookup_finds_nodes_by_meta_tag():
    index = SuperIndex()
    node = index.register({"tree": 1.0, "sky": 0.5})

    assert node.node_id in index.lookup(["tree"])


def test_direct_connection_is_bidirectional():
    index = SuperIndex()
    left = index.register({"tree": 1.0})
    right = index.register({"sky": 1.0})

    index.connect(left.node_id, right.node_id)

    assert right.node_id in left.box.known_connections
    assert left.node_id in right.box.known_connections


def test_ranking_is_query_relative():
    index = SuperIndex()
    tree = index.register({"tree": 1.0})
    sky = index.register({"sky": 1.0})

    ranked = index.rank({"sky": 1.0})

    assert ranked[0][0] == sky.node_id
    assert ranked[1][0] == tree.node_id
