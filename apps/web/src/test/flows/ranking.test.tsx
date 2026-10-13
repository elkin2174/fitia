import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ME, PROFILE } from "../fixtures";
import { renderRoute } from "../render";
import { API, http, ok, sent, server } from "../server";

const ITEMS = [
  { position: 1, nickname: "Gacela", points: 120, level: 3 },
  { position: 2, nickname: "Pantera", points: 90, level: 2 },
  { position: 3, nickname: "Cóndor", points: 60, level: 2 },
  { position: 4, nickname: "Tortuga", points: 10, level: 1 },
];

describe("ranking público", () => {
  it("es público: sin sesión muestra el podio y la lista, sin consultar el perfil", async () => {
    server.use(http.get(`${API}/ranking`, () => ok({ items: ITEMS })));
    renderRoute("/ranking");
    expect(await screen.findByRole("list", { name: "Podio" })).toBeInTheDocument();
    expect(screen.getByText("Gacela")).toBeInTheDocument();
    expect(screen.getByText("Tortuga")).toBeInTheDocument();
    expect(sent("GET", "/profile")).toHaveLength(0);
  });

  it("con sesión y oculto, explica que solo él ve su posición", async () => {
    server.use(
      http.get(`${API}/ranking`, () => ok({ items: [] })),
      http.get(`${API}/profile`, () => ok({ profile: { ...PROFILE, is_public_ranking: false, ranking_position: 7, points: 15 } })),
    );
    renderRoute("/ranking", { me: ME });
    expect(await screen.findByText(/Estás oculto del ranking público/)).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();
    expect(screen.getByText("El ranking está por arrancar")).toBeInTheDocument();
  });
});
