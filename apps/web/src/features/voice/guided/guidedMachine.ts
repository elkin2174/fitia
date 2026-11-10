export type GuidedStatus =
  | "idle"
  | "announcing"
  | "working"
  | "resting"
  | "paused"
  | "finished";

export type GuidedEvent =
  | { type: "start" }
  | { type: "reset"; exercises: readonly GuidedExerciseConfig[] }
  | { type: "speechEnded" }
  | { type: "timerEnded" }
  | { type: "done" }
  | { type: "next" }
  | { type: "previous" }
  | { type: "repeat" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "exit" };

export interface GuidedExerciseConfig {
  id: string;
  name: string;
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_seconds: number;
}

export interface GuidedState {
  readonly status: GuidedStatus;
  readonly exerciseIndex: number;
  readonly currentSet: number;
  readonly totalSets: number;
  readonly previousStatus: GuidedStatus | null;
  readonly exercises: readonly GuidedExerciseConfig[];
  readonly announcementKey: number;
}

export function createInitialGuidedState(
  exercises: readonly GuidedExerciseConfig[],
): GuidedState {
  const first = exercises[0];
  return {
    status: "idle",
    exerciseIndex: 0,
    currentSet: 1,
    totalSets: first ? Math.max(1, first.sets) : 1,
    previousStatus: null,
    exercises,
    announcementKey: 0,
  };
}

/**
 * Función PURA sin efectos secundarios: (estado, evento) -> nuevo estado.
 * Implementa la máquina de estados del modo guiado de entrenamiento.
 */
export function guidedMachine(state: GuidedState, event: GuidedEvent): GuidedState {
  if (event.type === "reset") {
    return createInitialGuidedState(event.exercises);
  }

  const { exercises, exerciseIndex, currentSet, totalSets, status, previousStatus } = state;

  switch (status) {
    case "idle": {
      if (event.type === "start" && exercises.length > 0) {
        const first = exercises[0]!;
        return {
          ...state,
          status: "announcing",
          exerciseIndex: 0,
          currentSet: 1,
          totalSets: Math.max(1, first.sets),
          previousStatus: null,
          announcementKey: state.announcementKey + 1,
        };
      }
      return state;
    }

    case "announcing": {
      switch (event.type) {
        case "speechEnded":
          return {
            ...state,
            status: "working",
          };

        case "pause":
          return {
            ...state,
            status: "paused",
            previousStatus: "announcing",
          };

        case "repeat":
          return {
            ...state,
            status: "announcing",
            announcementKey: state.announcementKey + 1,
          };

        case "next": {
          if (exerciseIndex < exercises.length - 1) {
            const nextIdx = exerciseIndex + 1;
            const nextEx = exercises[nextIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: nextIdx,
              currentSet: 1,
              totalSets: Math.max(1, nextEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "previous": {
          if (exerciseIndex > 0) {
            const prevIdx = exerciseIndex - 1;
            const prevEx = exercises[prevIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: prevIdx,
              currentSet: 1,
              totalSets: Math.max(1, prevEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "exit":
          return {
            ...state,
            status: "idle",
            previousStatus: null,
          };

        default:
          return state;
      }
    }

    case "working": {
      switch (event.type) {
        case "done":
        case "timerEnded":
          return {
            ...state,
            status: "resting",
          };

        case "pause":
          return {
            ...state,
            status: "paused",
            previousStatus: "working",
          };

        case "repeat":
          return {
            ...state,
            status: "announcing",
            announcementKey: state.announcementKey + 1,
          };

        case "next": {
          if (exerciseIndex < exercises.length - 1) {
            const nextIdx = exerciseIndex + 1;
            const nextEx = exercises[nextIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: nextIdx,
              currentSet: 1,
              totalSets: Math.max(1, nextEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "previous": {
          if (exerciseIndex > 0) {
            const prevIdx = exerciseIndex - 1;
            const prevEx = exercises[prevIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: prevIdx,
              currentSet: 1,
              totalSets: Math.max(1, prevEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "exit":
          return {
            ...state,
            status: "idle",
            previousStatus: null,
          };

        default:
          return state;
      }
    }

    case "resting": {
      switch (event.type) {
        case "done":
        case "timerEnded": {
          // Si quedan series en el ejercicio actual
          if (currentSet < totalSets) {
            return {
              ...state,
              status: "announcing",
              currentSet: currentSet + 1,
              announcementKey: state.announcementKey + 1,
            };
          }

          // Última serie del ejercicio actual: ¿quedan más ejercicios?
          if (exerciseIndex < exercises.length - 1) {
            const nextIdx = exerciseIndex + 1;
            const nextEx = exercises[nextIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: nextIdx,
              currentSet: 1,
              totalSets: Math.max(1, nextEx.sets),
              announcementKey: state.announcementKey + 1,
            };
          }

          // Última serie del último ejercicio: rutina finalizada
          return {
            ...state,
            status: "finished",
          };
        }

        case "pause":
          return {
            ...state,
            status: "paused",
            previousStatus: "resting",
          };

        case "repeat":
          return {
            ...state,
            status: "announcing",
            announcementKey: state.announcementKey + 1,
          };

        case "next": {
          if (exerciseIndex < exercises.length - 1) {
            const nextIdx = exerciseIndex + 1;
            const nextEx = exercises[nextIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: nextIdx,
              currentSet: 1,
              totalSets: Math.max(1, nextEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "previous": {
          if (exerciseIndex > 0) {
            const prevIdx = exerciseIndex - 1;
            const prevEx = exercises[prevIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: prevIdx,
              currentSet: 1,
              totalSets: Math.max(1, prevEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "exit":
          return {
            ...state,
            status: "idle",
            previousStatus: null,
          };

        default:
          return state;
      }
    }

    case "paused": {
      switch (event.type) {
        case "resume":
          return {
            ...state,
            status: previousStatus ?? "announcing",
            previousStatus: null,
          };

        case "repeat":
          return {
            ...state,
            status: "announcing",
            previousStatus: null,
            announcementKey: state.announcementKey + 1,
          };

        case "next": {
          if (exerciseIndex < exercises.length - 1) {
            const nextIdx = exerciseIndex + 1;
            const nextEx = exercises[nextIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: nextIdx,
              currentSet: 1,
              totalSets: Math.max(1, nextEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "previous": {
          if (exerciseIndex > 0) {
            const prevIdx = exerciseIndex - 1;
            const prevEx = exercises[prevIdx]!;
            return {
              ...state,
              status: "announcing",
              exerciseIndex: prevIdx,
              currentSet: 1,
              totalSets: Math.max(1, prevEx.sets),
              previousStatus: null,
              announcementKey: state.announcementKey + 1,
            };
          }
          return state;
        }

        case "exit":
          return {
            ...state,
            status: "idle",
            previousStatus: null,
          };

        default:
          return state;
      }
    }

    case "finished": {
      switch (event.type) {
        case "repeat": {
          const first = exercises[0];
          return {
            ...state,
            status: "announcing",
            exerciseIndex: 0,
            currentSet: 1,
            totalSets: first ? Math.max(1, first.sets) : 1,
            previousStatus: null,
          };
        }

        case "exit":
          return {
            ...state,
            status: "idle",
            previousStatus: null,
          };

        default:
          return state;
      }
    }

    default:
      return state;
  }
}
