import { api } from "../../shared/api/client";
import type { RankingResponse } from "../../shared/api/types";

export const rankingApi = {
  list: (limit = 100) => api.get<RankingResponse>(`/ranking?limit=${limit}`),
};
