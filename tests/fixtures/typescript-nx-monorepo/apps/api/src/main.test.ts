import { describe, it, expect } from "vitest";
import { formatAnimalId } from "@crv/shared";

describe("formatAnimalId", () => {
  it("uppercases the country prefix", () => {
    expect(formatAnimalId("nl123")).toBe("NL123");
  });
});
