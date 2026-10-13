import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PROGRAMS } from "../fixtures";
import { renderRoute, pathOf } from "../render";
import { API, apiError, http, ok, sent, server } from "../server";

async function fillValidForm(user: ReturnType<typeof renderRoute>["user"]) {
  await user.type(screen.getByLabelText("Apodo"), "Pantera");
  await user.type(screen.getByLabelText("Correo institucional"), "  Ana.Gomez@CorreoUnivalle.edu.co ");
  await user.type(screen.getByLabelText("Contraseña"), "contrasena-segura");
  await user.click(screen.getByRole("combobox", { name: "Programa académico" }));
  await user.type(screen.getByRole("combobox", { name: "Programa académico" }), "siste");
  await user.click(await screen.findByRole("option", { name: "Ingeniería de Sistemas" }));
  await user.click(screen.getByRole("checkbox", { name: /Acepto el tratamiento/ }));
}

describe("HU 1 — registro", () => {
  it("en cliente muestra todos los errores juntos sin llamar a la API", async () => {
    server.use(http.get(`${API}/programs`, () => ok(PROGRAMS)));
    const { user } = renderRoute("/registro");
    await user.click(await screen.findByRole("button", { name: "Crear mi cuenta" }));

    expect(await screen.findByText("Tu apodo debe tener entre 3 y 20 caracteres.")).toBeInTheDocument();
    expect(screen.getByText("Revisa el formato de tu correo.")).toBeInTheDocument();
    expect(screen.getByText("La contraseña debe tener al menos 8 caracteres.")).toBeInTheDocument();
    expect(screen.getByText("Elige tu programa académico.")).toBeInTheDocument();
    expect(screen.getByText("Debes aceptar el tratamiento de datos para continuar.")).toBeInTheDocument();
    expect(sent("POST", "/auth/register")).toHaveLength(0);
  });

  it("muestra a la vez todos los errores de campo que devuelve el backend", async () => {
    server.use(
      http.get(`${API}/programs`, () => ok(PROGRAMS)),
      http.post(`${API}/auth/register`, () =>
        apiError(422, "VALIDATION_ERROR", "Revisa los campos.", [
          { field: "nickname", code: "NICKNAME_LENGTH" },
          { field: "program_code", code: "PROGRAM_REQUIRED" },
          { field: "password", code: "WEAK_PASSWORD" },
        ]),
      ),
    );
    const { user } = renderRoute("/registro");
    await screen.findByLabelText("Apodo");
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Crear mi cuenta" }));

    expect(await screen.findByText("Tu apodo debe tener entre 3 y 20 caracteres.")).toBeInTheDocument();
    expect(screen.getByText("Elige tu programa académico.")).toBeInTheDocument();
    expect(screen.getByText("La contraseña debe tener al menos 8 caracteres.")).toBeInTheDocument();
    expect(screen.getByLabelText("Apodo")).toHaveAttribute("aria-invalid", "true");
  });

  it("envía el cuerpo con los tipos correctos (accepted_terms booleano) y lleva a revisar el correo", async () => {
    server.use(
      http.get(`${API}/programs`, () => ok(PROGRAMS)),
      http.post(`${API}/auth/register`, () => ok({ status: "pending_verification" }, 201)),
    );
    const { user, router } = renderRoute("/registro");
    await screen.findByLabelText("Apodo");
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Crear mi cuenta" }));

    await waitFor(() => expect(pathOf(router)).toBe("/registro/revisa-tu-correo"));
    const [request] = sent("POST", "/auth/register");
    expect(request?.body).toEqual({
      nickname: "Pantera",
      email: "ana.gomez@correounivalle.edu.co",
      password: "contrasena-segura",
      program_code: "ING-SIS",
      accepted_terms: true,
    });
    expect(request?.headers["x-requested-with"]).toBe("fitia");
    expect(await screen.findByText("ana.gomez@correounivalle.edu.co")).toBeInTheDocument();
  });

  it("409 EMAIL_EXISTS marca el correo y ofrece iniciar sesión", async () => {
    server.use(
      http.get(`${API}/programs`, () => ok(PROGRAMS)),
      http.post(`${API}/auth/register`, () =>
        apiError(409, "EMAIL_EXISTS", "Ya existe una cuenta.", [{ field: "email", code: "EMAIL_EXISTS" }]),
      ),
    );
    const { user } = renderRoute("/registro");
    await screen.findByLabelText("Apodo");
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Crear mi cuenta" }));

    expect(await screen.findAllByText("Este correo ya tiene cuenta.")).not.toHaveLength(0);
    // Uno en la cabecera y otro en el aviso del formulario.
    expect(screen.getAllByRole("link", { name: "Iniciar sesión" })).toHaveLength(2);
  });

  it("el reenvío muestra un mensaje neutro y un enfriamiento de 60 s", async () => {
    server.use(http.post(`${API}/auth/resend-verification`, () => ok({ status: "accepted", message: "x" }, 202)));
    const { user } = renderRoute("/registro/revisa-tu-correo");
    const button = await screen.findByRole("button", { name: "Reenviar enlace" });
    expect(button).toBeDisabled(); // sin correo conocido, primero hay que escribirlo
    await user.type(screen.getByLabelText("Tu correo institucional"), "ana@correounivalle.edu.co");
    await user.click(button);

    expect(await screen.findByText(/Si hay una cuenta pendiente con ese correo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reenviar enlace \(60 s\)/ })).toBeDisabled();
    expect(sent("POST", "/auth/resend-verification")[0]?.body).toEqual({ email: "ana@correounivalle.edu.co" });
  });
});
