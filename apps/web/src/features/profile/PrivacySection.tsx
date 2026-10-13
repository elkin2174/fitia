import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../../shared/ui/Feedback";
import { Switch } from "../../shared/ui/Switch";
import { useToast } from "../../shared/ui/Toast";
import { profileApi, profileKey } from "./api";
import type { ProfileResponse, StudentProfile } from "./types";

/** Se guarda al instante al tocar el interruptor, con actualización optimista y reversión si falla. */
export function PrivacySection({ profile }: { profile: StudentProfile }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const toggle = useMutation({
    mutationFn: (value: boolean) => profileApi.update({ is_public_ranking: value }),
    onMutate: async (value) => {
      await queryClient.cancelQueries({ queryKey: profileKey });
      const previous = queryClient.getQueryData<ProfileResponse>(profileKey);
      if (previous) queryClient.setQueryData<ProfileResponse>(profileKey, { profile: { ...previous.profile, is_public_ranking: value } });
      return { previous };
    },
    onSuccess: (result, value) => {
      queryClient.setQueryData<ProfileResponse>(profileKey, { profile: result.profile });
      void queryClient.invalidateQueries({ queryKey: ["ranking"] });
      toast(value ? "Ahora apareces en el ranking público." : "Ya no apareces en el ranking público.");
    },
    onError: (_error, _value, context) => {
      if (context?.previous) queryClient.setQueryData(profileKey, context.previous);
      toast("No pudimos cambiar tu privacidad. Intenta de nuevo.", "danger");
    },
  });

  return (
    <Card aria-labelledby="privacy-title" id="privacidad">
      <h2 id="privacy-title" className="mb-4 text-xl font-bold">
        Privacidad
      </h2>
      <Switch
        label="Aparecer en el ranking público"
        checked={profile.is_public_ranking}
        disabled={toggle.isPending}
        onChange={(value) => toggle.mutate(value)}
        description="Si te ocultas, conservas tus puntos y tu nivel, y sigues viendo tu posición de forma privada."
      />
    </Card>
  );
}
