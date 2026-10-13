import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { isApiError } from "../../shared/api/client";
import { formatDateFromTimestamp } from "../../shared/lib/dates";
import { fieldMessage } from "../../shared/lib/fieldErrors";
import { Banner } from "../../shared/ui/Banner";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { Card } from "../../shared/ui/Feedback";
import { TextField } from "../../shared/ui/TextField";
import { measurementsKey, profileApi, profileKey } from "./api";
import { diffProfile, hasChanges } from "./changes";
import { HEIGHT_RANGE_CM, WEIGHT_RANGE_KG, type ProfileResponse, type StudentProfile } from "./types";

const fmt = (n: number | null) => (n === null ? "" : String(n));
const parse = (text: string): number | null => {
  const normalized = text.trim().replace(",", ".");
  if (!normalized) return null;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : NaN;
};

export function PhysicalSection({ profile, onDirtyChange }: { profile: StudentProfile; onDirtyChange: (dirty: boolean) => void }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [weight, setWeight] = useState(fmt(profile.weight_kg));
  const [height, setHeight] = useState(fmt(profile.height_cm));
  const [errors, setErrors] = useState<{ weight_kg?: string; height_cm?: string }>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [saved, setSaved] = useState(false);

  const weightValue = parse(weight);
  const heightValue = parse(height);
  const changes = diffProfile(profile, { weight_kg: weightValue, height_cm: heightValue });
  const dirty = editing && (hasChanges(changes) || Number.isNaN(weightValue) || Number.isNaN(heightValue));
  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const save = useMutation({
    mutationFn: () => profileApi.update(changes),
    onSuccess: (result) => {
      queryClient.setQueryData<ProfileResponse>(profileKey, { profile: result.profile });
      void queryClient.invalidateQueries({ queryKey: measurementsKey });
      setEditing(false);
      setSaved(true);
    },
    onError: (error) => {
      if (isApiError(error, "VALIDATION_ERROR")) {
        const next: typeof errors = {};
        for (const f of error.fields) {
          if (f.field === "weight_kg" || f.field === "height_cm") next[f.field] = fieldMessage(f.field, f.code);
        }
        setErrors(next);
      }
    },
  });

  const validate = () => {
    const next: typeof errors = {};
    if (weightValue !== null && (Number.isNaN(weightValue) || weightValue < WEIGHT_RANGE_KG.min || weightValue > WEIGHT_RANGE_KG.max)) {
      next.weight_kg = fieldMessage("weight_kg", "INVALID_OPTION");
    }
    if (heightValue !== null && (Number.isNaN(heightValue) || heightValue < HEIGHT_RANGE_CM.min || heightValue > HEIGHT_RANGE_CM.max)) {
      next.height_cm = fieldMessage("height_cm", "INVALID_OPTION");
    }
    // El backend no permite borrar un dato ya registrado.
    if (weightValue === null && profile.weight_kg !== null) next.weight_kg = fieldMessage("weight_kg", "REQUIRED");
    if (heightValue === null && profile.height_cm !== null) next.height_cm = fieldMessage("height_cm", "REQUIRED");
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const start = () => {
    setWeight(fmt(profile.weight_kg));
    setHeight(fmt(profile.height_cm));
    setErrors({});
    setSaved(false);
    save.reset();
    setEditing(true);
  };
  const discard = () => {
    setEditing(false);
    setConfirmDiscard(false);
    setErrors({});
    save.reset();
  };

  const empty = profile.weight_kg === null && profile.height_cm === null;

  return (
    <Card aria-labelledby="physical-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="physical-title" className="text-xl font-bold">
          Datos físicos
        </h2>
        {!editing && !empty && (
          <Button variant="secondary" onClick={start}>
            Editar
          </Button>
        )}
      </div>

      {saved && !editing && <Banner tone="success" className="mt-4">Tus datos físicos se guardaron.</Banner>}

      {!editing && empty && (
        <div className="mt-4 flex flex-col items-start gap-3">
          <p className="text-muted">Aún no has registrado tu peso ni tu estatura.</p>
          <Button onClick={start}>Agregar mis datos</Button>
        </div>
      )}

      {!editing && !empty && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted">Peso</dt>
              <dd className="font-display text-2xl font-bold">{profile.weight_kg !== null ? `${profile.weight_kg} kg` : "Sin dato"}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted">Estatura</dt>
              <dd className="font-display text-2xl font-bold">{profile.height_cm !== null ? `${profile.height_cm} cm` : "Sin dato"}</dd>
            </div>
          </dl>
          {profile.physical_updated_at && (
            <p className="mt-3 text-sm text-muted">Actualizado el {formatDateFromTimestamp(profile.physical_updated_at)}</p>
          )}
        </>
      )}

      {editing && (
        <form
          noValidate
          className="mt-4 flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (!validate()) return;
            if (!hasChanges(changes)) return discard();
            save.mutate();
          }}
        >
          {save.isError && !isApiError(save.error, "VALIDATION_ERROR") && (
            <Banner tone="danger" live="assertive">{save.error.message}</Banner>
          )}
          <div className="grid gap-5 sm:grid-cols-2">
            <TextField
              label="Peso (kg)"
              inputMode="decimal"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              hint={`Entre ${WEIGHT_RANGE_KG.min} y ${WEIGHT_RANGE_KG.max} kg; puedes usar decimales.`}
              error={errors.weight_kg}
            />
            <TextField
              label="Estatura (cm)"
              inputMode="decimal"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              hint={`Entre ${HEIGHT_RANGE_CM.min} y ${HEIGHT_RANGE_CM.max} cm.`}
              error={errors.height_cm}
            />
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => (dirty ? setConfirmDiscard(true) : discard())} disabled={save.isPending}>
              Cancelar
            </Button>
            <Button type="submit" loading={save.isPending} loadingText="Guardando…">
              Guardar datos físicos
            </Button>
          </div>
        </form>
      )}

      <Link to="/perfil/historial" className="mt-4 inline-flex min-h-11 items-center font-bold text-primary-text underline">
        Ver historial
      </Link>

      <ConfirmDialog
        open={confirmDiscard}
        title="¿Descartar los cambios?"
        confirmLabel="Descartar cambios"
        cancelLabel="Seguir editando"
        onConfirm={discard}
        onCancel={() => setConfirmDiscard(false)}
      >
        Volverás a ver tus datos guardados.
      </ConfirmDialog>
    </Card>
  );
}
