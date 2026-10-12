import httpx



async def test_lista_de_programas_es_publica_y_ordenada_por_nombre(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/programs", headers={"X-Requested-With": ""})

    assert response.status_code == 200
    programs = response.json()
    assert len(programs) > 0
    assert all(set(p) == {"code", "name"} for p in programs)
    names = [p["name"] for p in programs]
    assert names == sorted(names, key=str.casefold)  # el orden lo define la collation de la BD
    assert {"code": "ING-SIS", "name": "Ingeniería de Sistemas"} in programs
