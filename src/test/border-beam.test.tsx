import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BorderBeam } from "@/components/ui/border-beam";

describe("Orbiting border beam", () => {
  it("renders a decorative perimeter highlight with a configurable animation", () => {
    const { container } = render(<div className="relative"><BorderBeam duration={8} size={100} radius={20} /></div>);
    const beam = container.querySelector(".noethara-border-beam__light");
    expect(beam?.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(beam?.getAttribute("rx")).toBe("20");
    expect((beam as SVGElement)?.style.animationDuration).toBe("8s");
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
