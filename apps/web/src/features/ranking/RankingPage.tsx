import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Page } from "../../app/AppLayout";
import type { RankingItem } from "../../shared/api/types";
import { cx } from "../../shared/lib/cx";
import { useMe } from "../../shared/session/session";
import { ButtonLink } from "../../shared/ui/Button";
import { Card, EmptyState, ErrorState, PageSkeleton } from "../../shared/ui/Feedback";
import { profileApi, profileKey } from "../profile/api";
import { rankingApi } from "./api";

export function RankingPage() {
  const me = useMe();
  const ranking = useQuery({ queryKey: ["ranking"], queryFn: () => rankingApi.list(100) });
  // Con sesión y diagnóstico, se consulta el perfil para mostrar "Tu posición" (sin redirigir si falla).
  const withProfile = Boolean(me.data?.onboarding_completed);
  const profile = useQuery({
    queryKey: profileKey,
    queryFn: () => profileApi.get({ silentAuth: true }),
    enabled: withProfile,
  });
  const own = profile.data?.profile;

  return (
    <Page>
      <h1 className="text-3xl font-extrabold">Ranking</h1>
      <p className="mt-2 text-muted">Constancia que se nota. Cada entrenamiento suma.</p>

      {withProfile && own && (
        <Card className="mt-6" aria-labelledby="own-position">
          <h2 id="own-position" className="font-bold">
            Tu posición: <span className="font-display text-2xl">{own.ranking_position ? `#${own.ranking_position}` : "—"}</span>
          </h2>
          <p className="text-muted">
            {own.points} puntos, nivel {own.level}
          </p>
          {!own.is_public_ranking && (
            <p className="mt-2">
              Estás oculto del ranking público. Solo tú ves tu posición.{" "}
              <Link to="/perfil#privacidad" className="font-bold text-primary-text underline">
                Cambiar privacidad
              </Link>
            </p>
          )}
        </Card>
      )}
      {me.data === null && (
        <p className="mt-4">
          <Link to="/registro" className="font-bold text-primary-text underline">
            Crea tu cuenta
          </Link>{" "}
          para aparecer en el ranking.
        </p>
      )}

      <div className="mt-6">
        {ranking.isPending && <PageSkeleton label="Cargando el ranking…" rows={4} />}
        {ranking.isError && <ErrorState message={ranking.error.message} onRetry={() => ranking.refetch()} />}
        {ranking.isSuccess && ranking.data.items.length === 0 && (
          <EmptyState
            title="El ranking está por arrancar"
            action={!me.data && <ButtonLink to="/registro">Crear mi cuenta</ButtonLink>}
          >
            Todavía nadie aparece aquí. Los puntos llegarán con los entrenamientos completados.
          </EmptyState>
        )}
        {ranking.isSuccess && ranking.data.items.length > 0 && (
          <RankingList items={ranking.data.items} highlight={own?.is_public_ranking ? own.ranking_position : null} />
        )}
      </div>
    </Page>
  );
}

function RankingList({ items, highlight }: { items: RankingItem[]; highlight: number | null | undefined }) {
  const podium = items.slice(0, 3);
  const rest = items.slice(3);
  return (
    <div className="flex flex-col gap-4">
      <ol className="grid grid-cols-3 items-end gap-2" aria-label="Podio">
        {[podium[1], podium[0], podium[2]].map((item, i) =>
          item ? (
            <li
              key={item.position}
              className={cx(
                "flex flex-col items-center rounded-t-[var(--radius-card)] px-2 pb-3 pt-4 text-center",
                item.position === 1 ? "bg-primary text-on-primary lane-stripes min-h-40" : "bg-surface-2 min-h-32",
                item.position === highlight && "ring-3 ring-focus",
              )}
            >
              <span className="font-display text-3xl font-extrabold" aria-label={`Posición ${item.position}`}>{item.position}</span>
              <span className="mt-1 w-full truncate font-bold">{item.nickname}</span>
              <span className="text-sm">{item.points} pts</span>
            </li>
          ) : (
            <li key={`empty-${i}`} aria-hidden="true" />
          ),
        )}
      </ol>
      {rest.length > 0 && (
        <Card as="div" className="p-0 sm:p-0">
          <ol aria-label="Resto del ranking" className="divide-y divide-line">
            {rest.map((item) => (
              <li
                key={item.position}
                aria-current={item.position === highlight ? "true" : undefined}
                className={cx("flex items-center gap-4 px-5 py-3", item.position === highlight && "bg-info-soft")}
              >
                <span className="w-10 font-display text-xl font-bold text-muted">{item.position}</span>
                <span className="flex-1 truncate font-bold">{item.nickname}</span>
                <span className="text-sm text-muted">Nivel {item.level}</span>
                <span className="w-16 text-right font-bold tabular-nums">{item.points} pts</span>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  );
}
