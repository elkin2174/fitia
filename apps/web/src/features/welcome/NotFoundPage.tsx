import { Page } from "../../app/AppLayout";
import { ButtonLink } from "../../shared/ui/Button";

export function NotFoundPage() {
  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Esta página no existe</h1>
      <p className="mt-2 text-muted">Revisa la dirección o vuelve al inicio.</p>
      <ButtonLink to="/" className="mt-6">
        Volver al inicio
      </ButtonLink>
    </Page>
  );
}
