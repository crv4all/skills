import Fastify from "fastify";
// Trap: @crv/shared is imported here but not declared in apps/api/package.json.
// pnpm's strict node_modules layout makes this fail at runtime where npm would
// have hoisted it and let it pass.
import { formatAnimalId } from "@crv/shared";

const app = Fastify();

app.get("/animals/:id", async (request) => {
  const { id } = request.params as { id: string };
  return { id: formatAnimalId(id) };
});

const port = Number(process.env.PORT ?? 3000);
app.listen({ port, host: process.env.HOST ?? "0.0.0.0" });
