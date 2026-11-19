import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HelmPanel } from "./HelmPanel";

describe("HelmPanel", () => {
  const helm = { course_deg: 20, speed_kn: 12, rudder: 0 };

  it("holds the rudder while an arrow is pressed and centres it on release", () => {
    const onHelm = vi.fn();
    render(<HelmPanel helm={helm} headingDeg={20} speedMps={6} onHelm={onHelm} />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    fireEvent.keyUp(window, { key: "ArrowRight" });
    expect(onHelm.mock.calls).toEqual([[{ rudder: 1 }], [{ rudder: 0 }]]);
  });

  it("leaves the arrows alone while the operator types", () => {
    const onHelm = vi.fn();
    render(
      <>
        <input aria-label="saisie" />
        <HelmPanel helm={helm} headingDeg={20} speedMps={6} onHelm={onHelm} />
      </>,
    );
    fireEvent.keyDown(screen.getByLabelText("saisie"), { key: "ArrowUp" });
    expect(onHelm).not.toHaveBeenCalled();
  });

  it("offers buttons for every step", async () => {
    const onHelm = vi.fn();
    render(<HelmPanel helm={helm} headingDeg={20} speedMps={6} onHelm={onHelm} />);
    for (const button of screen.getAllByRole("button")) await userEvent.click(button);
    expect(onHelm).toHaveBeenCalledTimes(5);
  });
});
