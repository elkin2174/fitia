import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { Page } from "../../app/AppLayout";
import { isApiError } from "../../shared/api/client";
import type { OptionCode } from "../../shared/api/types";
import { fieldMessage } from "../../shared/lib/fieldErrors";
import { useMe, useSessionActions } from "../../shared/session/session";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { Card, ErrorState, PageSkeleton, ProgressBar } from "../../shared/ui/Feedback";
import { AccountMenu } from "../profile/AccountMenu";
import { planApi, planKey } from "../plan/api";
import { onboardingApi, questionnaireKey, type Answers } from "./api";
import { QuestionField, answerLabel, isAnswered } from "./QuestionField";

export function DiagnosticPage() {
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const session = useSessionActions();
  const questionnaire = useQuery({ queryKey: questionnaireKey, queryFn: onboardingApi.questionnaire, staleTime: Infinity });

  // Las respuestas viven en memoria mientras se navega entre pasos (no hay borrador en el servidor).
  const [answers, setAnswers] = useState<Answers>({});
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const goToPlan = async () => {
    session.markOnboarding(true);
    try {
      await planApi.generate(); // la pantalla de inicio mostrará "armando tu plan"
    } catch {
      // 409/429/errores: la pantalla de inicio consulta el estado real y ofrece las acciones.
    }
    await queryClient.invalidateQueries({ queryKey: planKey });
    navigate("/inicio", { replace: true });
  };

  const submit = useMutation({
    mutationFn: () => onboardingApi.complete(answers),
    onSuccess: goToPlan,
    onError: (error) => {
      if (isApiError(error, "PROFILE_EXISTS")) {
        session.markOnboarding(true);
        navigate("/inicio", { replace: true });
        return;
      }
      if (isApiError(error, "VALIDATION_ERROR")) {
        const next: Record<string, string> = {};
        for (const f of error.fields) next[f.field] = fieldMessage(f.field, f.code);
        setErrors(next);
        const questions = questionnaire.data?.questions ?? [];
        const first = questions.findIndex((q) => next[q.id]);
        if (first >= 0) setStep(first);
      }
    },
  });

  if (me.data?.onboarding_completed && !submit.isPending && !submit.isSuccess) return <Navigate to="/inicio" replace />;

  if (questionnaire.isPending) {
    return (
      <Page>
        <PageSkeleton label="Cargando el diagnóstico…" rows={4} />
      </Page>
    );
  }
  if (questionnaire.isError) {
    return (
      <Page>
        <ErrorState message={questionnaire.error.message} onRetry={() => questionnaire.refetch()} />
      </Page>
    );
  }

  const questions = questionnaire.data.questions;
  const total = questions.length;
  const onSummary = step >= total;
  const question = questions[step];

  const setAnswer = (id: string, value: OptionCode | number[]) => {
    setAnswers((prev) => ({ ...prev, [id]: value }));
    setErrors((prev) => {
      const { [id]: _removed, ...rest } = prev;
      return rest;
    });
  };

  const next = () => {
    if (question && !isAnswered(question, answers[question.id])) {
      setErrors((prev) => ({
        ...prev,
        [question.id]: question.type === "multi" ? fieldMessage("training_days", "DAYS_REQUIRED") : "Elige una opción para continuar.",
      }));
      return;
    }
    setStep((s) => s + 1);
  };

  const saving = submit.isPending || submit.isSuccess;

  return (
    <Page>
      <div className="flex items-start justify-between gap-4">
        <div>
          {step === 0 && (
            <p className="font-bold text-primary-text">Hola, {me.data?.nickname ?? "deportista"}.</p>
          )}
          <h1 className="mt-1 text-3xl font-extrabold">
            {onSummary ? "Revisa tus respuestas" : "Cuéntanos un poco de ti para armar tu plan"}
          </h1>
        </div>
        <AccountMenu />
      </div>
      {step === 0 && (
        <p className="mt-2 text-muted">Son {total} preguntas rápidas. Solo las respondes una vez; luego puedes cambiarlas en tu perfil.</p>
      )}

      <div className="mt-6">
        <ProgressBar
          value={Math.min(step + 1, total)}
          max={total}
          label={onSummary ? "Todo listo para confirmar" : `Pregunta ${step + 1} de ${total}`}
        />
      </div>

      {submit.isError && !isApiError(submit.error, "PROFILE_EXISTS") && (
        <Banner tone="danger" live="assertive" className="mt-6">
          {submit.error.message}
        </Banner>
      )}

      {!onSummary && question && (
        <div className="mt-8">
          <h2 className="mb-4 text-2xl font-bold">{question.text}</h2>
          <QuestionField
            question={question}
            value={answers[question.id]}
            onChange={(value) => setAnswer(question.id, value)}
            error={errors[question.id]}
            hideLegend
          />
        </div>
      )}

      {onSummary && (
        <Card className="mt-8">
          <dl className="divide-y divide-line">
            {questions.map((q, index) => (
              <div key={q.id} className="grid grid-cols-[1fr_auto] items-center gap-x-3 py-3">
                <dt className="text-sm text-muted">{q.text}</dt>
                <dd className="col-start-1 font-bold">
                  {answerLabel(q, answers[q.id])}
                  {errors[q.id] && <span className="block text-sm text-danger">{errors[q.id]}</span>}
                </dd>
                <dd className="col-start-2 row-span-2 row-start-1">
                  <Button variant="ghost" onClick={() => setStep(index)} aria-label={`Cambiar: ${q.text}`}>
                    Cambiar
                  </Button>
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <div className="mt-8 flex gap-3">
        {step > 0 && (
          <Button variant="secondary" onClick={() => setStep((s) => s - 1)} disabled={saving}>
            Atrás
          </Button>
        )}
        {onSummary ? (
          <Button className="flex-1" onClick={() => submit.mutate()} loading={saving} loadingText="Guardando y armando tu plan…">
            Confirmar y armar mi plan
          </Button>
        ) : (
          <Button className="flex-1" onClick={next}>
            {step === total - 1 ? "Ver resumen" : "Siguiente"}
          </Button>
        )}
      </div>
    </Page>
  );
}
