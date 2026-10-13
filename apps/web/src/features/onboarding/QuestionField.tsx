import type { OptionCode, Question } from "../../shared/api/types";
import { DayChips } from "../../shared/ui/DayChips";
import { OptionCards } from "../../shared/ui/OptionCards";

interface QuestionFieldProps {
  question: Question;
  value: OptionCode | number[] | undefined;
  onChange: (value: OptionCode | number[]) => void;
  error?: string;
  hideLegend?: boolean;
}

/** Una pregunta del cuestionario, construida solo con lo que entrega la API. */
export function QuestionField({ question, value, onChange, error, hideLegend }: QuestionFieldProps) {
  if (question.type === "multi") {
    return (
      <DayChips
        legend={question.text}
        hideLegend={hideLegend}
        options={question.options}
        value={Array.isArray(value) ? value : []}
        onChange={onChange}
        error={error}
      />
    );
  }
  return (
    <OptionCards
      legend={question.text}
      hideLegend={hideLegend}
      options={question.options}
      value={Array.isArray(value) ? null : (value ?? null)}
      onChange={onChange}
      error={error}
      columns={question.options.length > 3 ? 2 : 1}
    />
  );
}

export function isAnswered(question: Question, value: OptionCode | number[] | undefined): boolean {
  if (question.type === "multi") return Array.isArray(value) && value.length > 0;
  return value !== undefined && !Array.isArray(value);
}

/** Etiqueta legible de una respuesta (para resúmenes). */
export function answerLabel(question: Question, value: OptionCode | number[] | undefined): string {
  if (Array.isArray(value)) {
    return question.options
      .filter((o) => value.some((v) => v === o.code))
      .map((o) => o.label)
      .join(", ");
  }
  return question.options.find((o) => o.code === value && typeof o.code === typeof value)?.label ?? "Sin responder";
}
