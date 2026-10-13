import { Suspense, lazy, type ComponentType } from "react";
import type { RouteObject } from "react-router";
import { PageSkeleton } from "../shared/ui/Feedback";
import { AppLayout } from "./AppLayout";
import { PublicOnly, RequireProfile, RequireSession } from "./guards";

function lazyPage(loader: () => Promise<Record<string, unknown>>, name: string) {
  const Component = lazy(async () => ({ default: (await loader())[name] as ComponentType }));
  return function LazyPage() {
    return (
      <Suspense fallback={<div className="mx-auto max-w-xl px-4 py-6"><PageSkeleton /></div>}>
        <Component />
      </Suspense>
    );
  };
}

const CheckEmailPage = lazyPage(() => import("../features/auth/CheckEmailPage"), "CheckEmailPage");
const LoginPage = lazyPage(() => import("../features/auth/LoginPage"), "LoginPage");
const RegisterPage = lazyPage(() => import("../features/auth/RegisterPage"), "RegisterPage");
const VerifyEmailPage = lazyPage(() => import("../features/auth/VerifyEmailPage"), "VerifyEmailPage");
const DiagnosticPage = lazyPage(() => import("../features/onboarding/DiagnosticPage"), "DiagnosticPage");
const HomePage = lazyPage(() => import("../features/plan/HomePage"), "HomePage");
const TodayPage = lazyPage(() => import("../features/plan/TodayPage"), "TodayPage");
const PlanDayPage = lazyPage(() => import("../features/plan/PlanDayPage"), "PlanDayPage");
const DeleteAccountPage = lazyPage(() => import("../features/profile/DeleteAccountPage"), "DeleteAccountPage");
const HistoryPage = lazyPage(() => import("../features/profile/HistoryPage"), "HistoryPage");
const ProfilePage = lazyPage(() => import("../features/profile/ProfilePage"), "ProfilePage");
const RankingPage = lazyPage(() => import("../features/ranking/RankingPage"), "RankingPage");
const NotFoundPage = lazyPage(() => import("../features/welcome/NotFoundPage"), "NotFoundPage");
const WelcomePage = lazyPage(() => import("../features/welcome/WelcomePage"), "WelcomePage");

export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <WelcomePage /> },
      { path: "/registro/revisa-tu-correo", element: <CheckEmailPage /> },
      { path: "/verificar-correo", element: <VerifyEmailPage /> },
      { path: "/ranking", element: <RankingPage /> },
      {
        element: <PublicOnly />,
        children: [
          { path: "/registro", element: <RegisterPage /> },
          { path: "/iniciar-sesion", element: <LoginPage /> },
        ],
      },
      {
        element: <RequireSession />,
        children: [
          { path: "/diagnostico", element: <DiagnosticPage /> },
          { path: "/perfil/eliminar-cuenta", element: <DeleteAccountPage /> },
        ],
      },
      {
        element: <RequireProfile />,
        children: [
          { path: "/inicio", element: <HomePage /> },
          { path: "/hoy", element: <TodayPage /> },
          { path: "/plan/dia/:fecha", element: <PlanDayPage /> },
          { path: "/perfil", element: <ProfilePage /> },
          { path: "/perfil/historial", element: <HistoryPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
