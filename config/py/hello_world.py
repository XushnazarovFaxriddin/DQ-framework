def build(vars):
    return {
        "connections": {"source_env_var": "PG_CONN", "target_env_var": "BQ_CONN"},
        "defaults": {"row_limit": 1000},
        "tables": [
            {
                "name": "ORDERS",
                "source": {"table": "public.orders"},
                "target": {"table": "project.dataset.orders"},
                "join_keys": {"source": ["id"], "target": ["id"]},
                "checks": [
                    {
                        "type": "hash_diff",
                        "include_map": {
                            "id": {"source": "id", "target": "id"},
                            "status": {
                                "source": "LOWER(status)",
                                "target": "LOWER(order_status)",
                            },
                            "amount": {
                                "source": "amount",
                                "target": "CAST(amount AS NUMERIC)",
                            },
                        },
                    }
                ],
            }
        ],
    }
