import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { isApiError } from "../../shared/api/client";
import type { OptionCode } from "../../shared/api/types";
import { fieldErrorsFrom } from "../../shared/lib/fieldErrors";
import { Banner } from "../../shared/ui/Banner";
import { Button, ButtonLink } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { Card, ErrorState, Skeleton } from "../../shared/ui/Feedback";
import { onboardingApi, questionnaireKey } from "../onboarding/api";
import { QuestionField, answerLabel } from "../onboarding/QuestionField";
import { planKey } from "../plan/api";
import { profileApi, profileKey } from "./api";
import { diffProfile, hasChanges } from "./changes";
import type { DiagnosticAnswers, ProfileResponse, StudentProfile } from "./types";

type Draft = Record<string, OptionCode | number[]>;

const toDraft = (profile: StudentProfile): Draft => ({
  goal: profile.goal,
  term_weeks: profile.term_weeks,
  fitness_level: profile.fitness_level,
  session_minutes: profile.session_minutes,
  training_days: [...profile.training_days],
  has_machine_access: profile.has_machine_access,
});

interface Props {
  profile: StudentProfile;
  onDirtyChange: (dirty: boolean) => void;
}

/**
 * "Mi diagnóstico" (HU 6). Opciones y etiquetas salen de GET /onboarding/questionnaire;
 * no hay listas locales. Solo se envían los campos que cambiaron.
 */
export function ProfileDiagnosticView({ profile, onDirtyChange }: Props) {
  const queryClient = useQueryClient();
  const questionnaire = useQuery({ queryKey: questionnaireKey, queryFn: onboardingApi.questionnaire, staleTime: Infinity });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => toDraft(profile));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const changes = diffProfile(profile, draft as Partial<DiagnosticAnswers>);
  const dirty = editing && hasChanges(changes);
  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const save = useMutation({
    mutationFn: () => profileApi.update(changes),
    onSuccess: (result) => {
      queryClient.setQueryData<ProfileResponse>(profileKey, { profile: result.profile });
      void queryClient.invalidateQueries({ queryKey: planKey }); // aparecerá "plan desactualizado"
      setSavedMessage(result.message);
      setEditing(false);
      setFieldErrors({});
    },
    onError: (error) => {
      // Todo o nada: el borrador del usuario se conserva y lo guardado no cambia.
      if (isApiError(error, "VALIDATION_ERROR")) setFieldErrors(fieldErrorsFrom(error));
    },
  });

  const startEditing = () => {
    setDraft(toDraft(profile));
    setFieldErrors({});
    setSavedMessage(null);
    save.reset();
    setEditing(true);
  };
  const discard = () => {
    setDraft(toDraft(profile));
    setEditing(false);
    setConfirmDiscard(false);
    setFieldErrors({});
    save.reset();
  };
  const onSave = () => {
    if (!hasChanges(changes)) {
      setEditing(false); // nada que guardar: no se envía la petición (evita EMPTY_UPDATE)
      return;
    }
    if (Array.isArray(draft.training_days) && draft.training_days.length === 0) {
      setFieldErrors({ training_days: "Elige al menos un día para entrenar, de lunes a viernes." });
      return;
    }
    save.mutate();
  };

  return (
    <Card aria-labelledby="diagnostic-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="diagnostic-title" className="text-xl font-bold">
          Mi diagnóstico
        </h2>
        {!editing && questionnaire.isSuccess && (
          <Button variant="secondary" onClick={startEditing}>
            Editar
          </Button>
        )}
      </div>

      {savedMessage && !editing && (
        <Banner tone="success" className="mt-4" actions={<ButtonLink to="/inicio" variant="secondary">Ir a mi plan</ButtonLink>}>
          {savedMessage}
        </Banner>
      )}

      {questionnaire.isPending && (
        <div className="mt-4 flex flex-col gap-3" role="status">
          <span className="sr-only">Cargando tu diagnóstico…</span>
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      )}
      {questionnaire.isError && (
        <div className="mt-4">
          <ErrorState message={questionnaire.error.message} onRetry={() => questionnaire.refetch()} />
        </div>
      )}

      {questionnaire.isSuccess && !editing && (
        <dl className="mt-4 divide-y divide-line">
          {questionnaire.data.questions.map((q) => (
            <div key={q.id} className="py-3">
              <dt className="text-sm text-muted">{q.text}</dt>
              <dd className="font-bold">{answerLabel(q, toDraft(profile)[q.id])}</dd>
            </div>
          ))}
        </dl>
      )}

      {questionnaire.isSuccess && editing && (
        <div className="mt-4 flex flex-col gap-7">
          <Banner tone="info">Tu plan actual no cambia: estos cambios se aplicarán al próximo plan que generes.</Banner>
          {save.isError && (
            <Banner tone="danger" live="assertive">
              {save.error.message}
            </Banner>
          )}
          {questionnaire.data.questions.map((q) => (
            <QuestionField
              key={q.id}
              question={q}
              value={draft[q.id]}
              onChange={(value) => {
                setDraft((d) => ({ ...d, [q.id]: value }));
                setFieldErrors(({ [q.id]: _removed, ...rest }) => rest);
              }}
              error={fieldErrors[q.id]}
            />
          ))}
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => (dirty ? setConfirmDiscard(true) : discard())} disabled={save.isPending}>
              Cancelar
            </Button>
            <Button onClick={onSave} loading={save.isPending} loadingText="Guardando…">
              Guardar diagnóstico
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDiscard}
        title="¿Descartar los cambios?"
        confirmLabel="Descartar cambios"
        cancelLabel="Seguir editando"
        onConfirm={discard}
        onCancel={() => setConfirmDiscard(false)}
      >
        Volverás a ver tus respuestas guardadas.
      </ConfirmDialog>
    </Card>
  );
}
