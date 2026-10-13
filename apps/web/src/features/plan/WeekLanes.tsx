import { Link } from "react-router";
import type { PlanDay } from "../../shared/api/types";
import { cx } from "../../shared/lib/cx";
import { WEEKDAY_NAMES, WEEKDAY_SHORT, formatDayMonth } from "../../shared/lib/dates";

/**
 * La semana como carriles de la pista del CDU: un carril por día, de lunes a viernes.
 * El día de hoy lleva el tartán rojo. Los días de entrenamiento enlazan al detalle (HU 12).
 */
export function WeekLanes({ days, today }: { days: PlanDay[]; today: string }) {
  return (
    <ol className="flex flex-col gap-2.5" aria-label="Tu semana de lunes a viernes">
      {days.map((day) => {
        const isToday = day.date === today;
        const name = WEEKDAY_NAMES[day.weekday] ?? "";
        const isTraining = day.status === "training";

        const label = `${name} ${formatDayMonth(day.date)}${isToday ? ", hoy" : ""}`;

        const articleContent = (
          <article
            aria-label={!isTraining ? label : undefined}
            aria-hidden={isTraining ? "true" : undefined}
            className={cx(
              "relative flex min-h-20 items-stretch overflow-hidden rounded-[var(--radius-card)] border-2 transition-colors",
              isToday ? "border-primary" : "border-line",
              day.status === "unplanned"
                ? "border-dashed bg-transparent"
                : "bg-surface",
              isTraining && "hover:border-primary/50 hover:bg-surface-2 cursor-pointer"
            )}
          >
            <div
              className={cx(
                "flex w-16 shrink-0 flex-col items-center justify-center font-display",
                isToday
                  ? "lane-stripes bg-primary text-on-primary"
                  : day.status === "rest"
                  ? "bg-rest-soft text-rest"
                  : "bg-surface-2 text-muted"
              )}
            >
              <span className="text-3xl font-extrabold leading-none" aria-hidden="true">
                {WEEKDAY_SHORT[day.weekday]}
              </span>
              <span className="mt-1 text-xs font-sans font-bold" aria-hidden="true">
                {isToday ? "Hoy" : formatDayMonth(day.date).replace(" de ", " ").slice(0, 6)}
              </span>
            </div>
            <div className="flex min-w-0 flex-1 items-center justify-between gap-3 px-4 py-3">
              <DayContent day={day} />
              {isTraining && (
                <svg
                  className="h-5 w-5 shrink-0 text-muted"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              )}
            </div>
          </article>
        );

        return (
          <li key={day.date}>
            {isTraining ? (
              <Link
                to={`/plan/dia/${day.date}`}
                aria-label={`${label}, ver rutina`}
                className="block no-underline focus-visible:outline-2 focus-visible:outline-primary rounded-[var(--radius-card)]"
              >
                {articleContent}
              </Link>
            ) : (
              articleContent
            )}
          </li>
        );
      })}
    </ol>
  );
}

function DayContent({ day }: { day: PlanDay }) {
  if (day.status === "training") {
    return (
      <div className="min-w-0">
        <p className="line-clamp-2 font-display text-lg font-bold leading-snug">{day.title}</p>
        <p className="flex items-center gap-1.5 text-muted">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <circle cx="12" cy="13" r="8" />
            <path d="M12 9v4l2.5 2M9 2h6" />
          </svg>
          {day.estimated_minutes} min
        </p>
      </div>
    );
  }
  if (day.status === "rest") {
    return (
      <div>
        <p className="font-display text-lg font-bold text-rest">Descanso</p>
        <p className="text-sm text-muted">Recuperar también es parte del plan.</p>
      </div>
    );
  }
  if (day.status === "completed") {
    return <p className="font-display text-lg font-bold text-success">Completado</p>;
  }
  return (
    <div>
      <p className="font-bold text-muted">Sin plan</p>
      <p className="text-sm text-muted">Este día ya había pasado cuando armamos tu plan.</p>
    </div>
  );
}
