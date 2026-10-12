import React, { useEffect, useState } from "react";
import { getProfile, updateProfile } from "./api";
import {
  FITNESS_LEVEL_OPTIONS,
  GOAL_OPTIONS,
  SESSION_MINUTES_OPTIONS,
  TERM_WEEKS_OPTIONS,
  WEEKDAY_OPTIONS,
  type DiagnosticProfile,
  type FitnessLevel,
  type Goal,
  type SessionMinutes,
  type TermWeeks,
  type Weekday,
} from "./types";

export const ProfileDiagnosticView: React.FC = () => {
  const [profile, setProfile] = useState<DiagnosticProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Estados del formulario para los 6 campos del diagnóstico
  const [goal, setGoal] = useState<Goal>("general_health");
  const [termWeeks, setTermWeeks] = useState<TermWeeks>(8);
  const [fitnessLevel, setFitnessLevel] = useState<FitnessLevel>("beginner");
  const [sessionMinutes, setSessionMinutes] = useState<SessionMinutes>(30);
  const [hasMachineAccess, setHasMachineAccess] = useState<boolean>(true);
  const [trainingDays, setTrainingDays] = useState<Weekday[]>([1, 3, 5]);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getProfile()
      .then((res) => {
        if (!isMounted) return;
        setProfile(res.profile);
        setGoal(res.profile.goal);
        setTermWeeks(res.profile.term_weeks);
        setFitnessLevel(res.profile.fitness_level);
        setSessionMinutes(res.profile.session_minutes);
        setHasMachineAccess(res.profile.has_machine_access);
        setTrainingDays(res.profile.training_days);
      })
      .catch((err) => {
        if (!isMounted) return;
        setErrorMessage(err.message || "Error al cargar tu diagnóstico actual.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleDayToggle = (day: Weekday) => {
    setTrainingDays((prev) =>
      prev.includes(day)
        ? prev.filter((d) => d !== day)
        : [...prev, day].sort((a, b) => a - b)
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    // Validación antes de enviar: al menos un día seleccionado
    if (trainingDays.length === 0) {
      setErrorMessage("Debes seleccionar al menos un día para entrenar de lunes a viernes.");
      return;
    }

    setSaving(true);
    try {
      const payload: DiagnosticProfile = {
        goal,
        term_weeks: termWeeks,
        fitness_level: fitnessLevel,
        session_minutes: sessionMinutes,
        has_machine_access: hasMachineAccess,
        training_days: trainingDays,
      };

      const res = await updateProfile(payload);
      setProfile(res.profile);
      setSuccessMessage(
        res.message ||
          "Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán al próximo plan que generes. Tu plan actual no ha cambiado."
      );
    } catch (err: any) {
      setErrorMessage(err.message || "No se pudo actualizar el diagnóstico.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-neutral-400">
        <p>Cargando información del diagnóstico...</p>
      </div>
    );
  }

  if (errorMessage && !profile) {
    return (
      <div className="rounded-lg bg-red-950/40 border border-red-800 p-4 text-red-200">
        <p className="font-semibold">Error al cargar el perfil</p>
        <p className="text-sm mt-1">{errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 bg-neutral-900 border border-neutral-800 rounded-xl shadow-lg">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white">Mi Diagnóstico Deportivo</h2>
        <p className="text-sm text-neutral-400 mt-1">
          Actualiza tus metas y disponibilidad. Tu apodo y programa académico se gestionan por separado.
        </p>
      </div>

      {successMessage && (
        <div className="mb-6 p-4 rounded-lg bg-emerald-950/50 border border-emerald-700 text-emerald-200">
          <p className="font-medium">{successMessage}</p>
        </div>
      )}

      {errorMessage && (
        <div className="mb-6 p-4 rounded-lg bg-red-950/50 border border-red-700 text-red-200">
          <p className="font-medium">{errorMessage}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 1. Objetivo */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            Objetivo principal
          </label>
          <select
            value={goal}
            onChange={(e) => setGoal(e.target.value as Goal)}
            disabled={saving}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
          >
            {GOAL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 2. Plazo */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            Plazo de la meta
          </label>
          <select
            value={termWeeks}
            onChange={(e) => setTermWeeks(Number(e.target.value) as TermWeeks)}
            disabled={saving}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
          >
            {TERM_WEEKS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 3. Nivel de condición física */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            Nivel de condición física
          </label>
          <select
            value={fitnessLevel}
            onChange={(e) => setFitnessLevel(e.target.value as FitnessLevel)}
            disabled={saving}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
          >
            {FITNESS_LEVEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 4. Duración de la sesión */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            Minutos por sesión
          </label>
          <select
            value={sessionMinutes}
            onChange={(e) => setSessionMinutes(Number(e.target.value) as SessionMinutes)}
            disabled={saving}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
          >
            {SESSION_MINUTES_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 5. Acceso a máquinas */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            ¿Tienes acceso a máquinas del gimnasio o CDU?
          </label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer text-neutral-300">
              <input
                type="radio"
                name="hasMachineAccess"
                checked={hasMachineAccess === true}
                onChange={() => setHasMachineAccess(true)}
                disabled={saving}
                className="text-red-600 focus:ring-red-600"
              />
              Sí, tengo acceso
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-neutral-300">
              <input
                type="radio"
                name="hasMachineAccess"
                checked={hasMachineAccess === false}
                onChange={() => setHasMachineAccess(false)}
                disabled={saving}
                className="text-red-600 focus:ring-red-600"
              />
              No, prefiero peso corporal
            </label>
          </div>
        </div>

        {/* 6. Días de entrenamiento */}
        <div>
          <label className="block text-sm font-medium text-neutral-200 mb-2">
            Días de entrenamiento (selecciona al menos uno)
          </label>
          <div className="grid grid-cols-5 gap-2">
            {WEEKDAY_OPTIONS.map((day) => {
              const selected = trainingDays.includes(day.value);
              return (
                <button
                  type="button"
                  key={day.value}
                  onClick={() => handleDayToggle(day.value)}
                  disabled={saving}
                  className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors border ${
                    selected
                      ? "bg-red-600 text-white border-red-500 shadow"
                      : "bg-neutral-800 text-neutral-300 border-neutral-700 hover:border-neutral-500"
                  } disabled:opacity-50`}
                >
                  {day.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Botón de guardado */}
        <div className="pt-4 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving ? "Guardando..." : "Guardar Cambios"}
          </button>
        </div>
      </form>
    </div>
  );
};
