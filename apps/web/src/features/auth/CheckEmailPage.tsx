import { useLocation } from "react-router";
import { Page } from "../../app/AppLayout";
import { Card } from "../../shared/ui/Feedback";
import { ResendVerification } from "./ResendVerification";

export function CheckEmailPage() {
  const email = (useLocation().state as { email?: string } | null)?.email;
  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Revisa tu correo</h1>
      <p className="mt-3">
        {email ? (
          <>
            Te enviamos un enlace a <strong className="break-all">{email}</strong> para activar tu cuenta.
          </>
        ) : (
          "Te enviamos un enlace a tu correo institucional para activar tu cuenta."
        )}
      </p>
      <Card className="mt-6">
        <h2 className="text-lg font-bold">¿No te llegó?</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          <li>Revisa la carpeta de spam o correo no deseado.</li>
          <li>El enlace vence en 24 horas y solo funciona una vez.</li>
          <li>Ábrelo en este mismo dispositivo para entrar directo.</li>
        </ul>
        <div className="mt-5">
          <ResendVerification email={email} />
        </div>
      </Card>
    </Page>
  );
}
