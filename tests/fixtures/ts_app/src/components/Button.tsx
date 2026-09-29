import React from "react";
import { Formatter } from "@lib/strings";
import loadSettings, { Level } from "@acme/config";
import { double as twice, add } from "../lib";
import "./button.css";

interface ButtonProps {
  label: string;
}

export const Button = ({ label }: ButtonProps) => {
  const settings = loadSettings();
  return <button data-level={Level.Low}>{new Formatter(settings.url).format(label)} {twice(add(1, 2))}</button>;
};

function Helper() {
  return <span>Don't break the lexer</span>;
}

export default function Page() {
  const lazy = import("../lib/math");
  const legacy = require("lodash/fp");
  return (
    <div>
      <Helper />
      <Button label="go" />
    </div>
  );
}
