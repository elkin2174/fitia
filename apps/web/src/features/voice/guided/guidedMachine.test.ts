import { describe, expect, it } from "vitest";
import {
  createInitialGuidedState,
  guidedMachine,
  type GuidedExerciseConfig,
} from "./guidedMachine";

describe("guidedMachine (máquina de estados pura)", () => {
  const sampleExercises: GuidedExerciseConfig[] = [
    {
      id: "ex-1",
      name: "Sentadilla libre",
      sets: 3,
      reps: 12,
      work_seconds: null,
      rest_seconds: 60,
    },
    {
      id: "ex-2",
      name: "Plancha frontal",
      sets: 3,
      reps: null,
      work_seconds: 30,
      rest_seconds: 45,
    },
    {
      id: "ex-3",
      name: "Flexiones de pecho",
      sets: 3,
      reps: 10,
      work_seconds: null,
      rest_seconds: 60,
    },
  ];

  it("inicialización correcta en estado idle", () => {
    const state = createInitialGuidedState(sampleExercises);
    expect(state.status).toBe("idle");
    expect(state.exerciseIndex).toBe(0);
    expect(state.currentSet).toBe(1);
    expect(state.totalSets).toBe(3);
    expect(state.previousStatus).toBeNull();
  });

  it("idle + start arranca en announcing con el primer ejercicio", () => {
    const initial = createInitialGuidedState(sampleExercises);
    const next = guidedMachine(initial, { type: "start" });
    expect(next.status).toBe("announcing");
    expect(next.exerciseIndex).toBe(0);
    expect(next.currentSet).toBe(1);
    expect(next.totalSets).toBe(3);
  });

  it("eventos inválidos en idle no tienen efecto", () => {
    const initial = createInitialGuidedState(sampleExercises);
    expect(guidedMachine(initial, { type: "speechEnded" })).toBe(initial);
    expect(guidedMachine(initial, { type: "done" })).toBe(initial);
    expect(guidedMachine(initial, { type: "timerEnded" })).toBe(initial);
    expect(guidedMachine(initial, { type: "pause" })).toBe(initial);
    expect(guidedMachine(initial, { type: "resume" })).toBe(initial);
    expect(guidedMachine(initial, { type: "next" })).toBe(initial);
    expect(guidedMachine(initial, { type: "previous" })).toBe(initial);
  });

  it("transición announcing -> working con speechEnded", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });
    expect(state.status).toBe("announcing");

    state = guidedMachine(state, { type: "speechEnded" });
    expect(state.status).toBe("working");
    expect(state.exerciseIndex).toBe(0);
    expect(state.currentSet).toBe(1);
  });

  it("transición working -> resting con done (ejercicio por repeticiones)", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });
    state = guidedMachine(state, { type: "speechEnded" });
    expect(state.status).toBe("working");

    state = guidedMachine(state, { type: "done" });
    expect(state.status).toBe("resting");
  });

  it("transición working -> resting con timerEnded (ejercicio por tiempo)", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });
    state = guidedMachine(state, { type: "speechEnded" });

    state = guidedMachine(state, { type: "timerEnded" });
    expect(state.status).toBe("resting");
  });

  it("resting -> announcing para la siguiente serie del mismo ejercicio", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" }); // Ex 0, Set 1, announcing
    state = guidedMachine(state, { type: "speechEnded" }); // working
    state = guidedMachine(state, { type: "done" }); // resting

    state = guidedMachine(state, { type: "timerEnded" });
    expect(state.status).toBe("announcing");
    expect(state.exerciseIndex).toBe(0);
    expect(state.currentSet).toBe(2);
    expect(state.totalSets).toBe(3);
  });

  it("pausa y reanudación desde cada estado activo (announcing, working, resting)", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" }); // announcing

    // 1. Pausa desde announcing
    state = guidedMachine(state, { type: "pause" });
    expect(state.status).toBe("paused");
    expect(state.previousStatus).toBe("announcing");
    state = guidedMachine(state, { type: "resume" });
    expect(state.status).toBe("announcing");
    expect(state.previousStatus).toBeNull();

    // 2. Pausa desde working
    state = guidedMachine(state, { type: "speechEnded" }); // working
    state = guidedMachine(state, { type: "pause" });
    expect(state.status).toBe("paused");
    expect(state.previousStatus).toBe("working");
    state = guidedMachine(state, { type: "resume" });
    expect(state.status).toBe("working");
    expect(state.previousStatus).toBeNull();

    // 3. Pausa desde resting
    state = guidedMachine(state, { type: "done" }); // resting
    state = guidedMachine(state, { type: "pause" });
    expect(state.status).toBe("paused");
    expect(state.previousStatus).toBe("resting");
    state = guidedMachine(state, { type: "resume" });
    expect(state.status).toBe("resting");
    expect(state.previousStatus).toBeNull();
  });

  it("navegación con next y previous respeta los límites de la rutina", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });
    expect(state.exerciseIndex).toBe(0);

    // previous en el primer ejercicio no cambia nada
    const atFirst = guidedMachine(state, { type: "previous" });
    expect(atFirst).toBe(state);

    // next avanza al ejercicio 1
    state = guidedMachine(state, { type: "next" });
    expect(state.exerciseIndex).toBe(1);
    expect(state.status).toBe("announcing");
    expect(state.currentSet).toBe(1);

    // next avanza al ejercicio 2 (último)
    state = guidedMachine(state, { type: "next" });
    expect(state.exerciseIndex).toBe(2);
    expect(state.status).toBe("announcing");

    // next en el último ejercicio no cambia nada
    const atLast = guidedMachine(state, { type: "next" });
    expect(atLast).toBe(state);

    // previous regresa al ejercicio 1
    state = guidedMachine(state, { type: "previous" });
    expect(state.exerciseIndex).toBe(1);
    expect(state.status).toBe("announcing");
  });

  it("repeat reinicia announcing en el ejercicio actual", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });
    state = guidedMachine(state, { type: "speechEnded" }); // working

    state = guidedMachine(state, { type: "repeat" });
    expect(state.status).toBe("announcing");
    expect(state.exerciseIndex).toBe(0);
    expect(state.currentSet).toBe(1);
  });

  it("exit desde cualquier estado regresa a idle", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" }); // announcing
    state = guidedMachine(state, { type: "exit" });
    expect(state.status).toBe("idle");

    state = guidedMachine(state, { type: "start" });
    state = guidedMachine(state, { type: "speechEnded" }); // working
    state = guidedMachine(state, { type: "exit" });
    expect(state.status).toBe("idle");

    state = guidedMachine(state, { type: "start" });
    state = guidedMachine(state, { type: "speechEnded" });
    state = guidedMachine(state, { type: "done" }); // resting
    state = guidedMachine(state, { type: "exit" });
    expect(state.status).toBe("idle");
  });

  it("recorrido completo de una rutina de 3 ejercicios con 3 series cada uno", () => {
    let state = createInitialGuidedState(sampleExercises);
    state = guidedMachine(state, { type: "start" });

    // Recorremos los 3 ejercicios
    for (let exIdx = 0; exIdx < sampleExercises.length; exIdx++) {
      expect(state.exerciseIndex).toBe(exIdx);

      // Recorremos las 3 series de cada ejercicio
      for (let set = 1; set <= 3; set++) {
        expect(state.status).toBe("announcing");
        expect(state.currentSet).toBe(set);

        // Termina de hablar -> working
        state = guidedMachine(state, { type: "speechEnded" });
        expect(state.status).toBe("working");

        // Termina el trabajo (por tiempo o repeticiones) -> resting
        state = guidedMachine(state, { type: "done" });
        expect(state.status).toBe("resting");

        // Termina el descanso
        state = guidedMachine(state, { type: "timerEnded" });
      }
    }

    // Al finalizar la última serie del último ejercicio, pasa a finished
    expect(state.status).toBe("finished");
  });
});
