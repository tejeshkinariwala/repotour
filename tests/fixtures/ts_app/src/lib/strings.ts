import type { Settings } from "../config";
import { add } from "./math.js";

const fake = "import x from 'y'";
const template = `function notReal() { return ${fake}; } ${`nested ${"deep"}`}`;
// function commentedOut() {}
/* function blockCommented() {} */
const pattern = /['"`]\/\/ not a comment/g;

export class Formatter {
  private prefix: string;
  static defaultPrefix = "acme";

  constructor(prefix: string) {
    this.prefix = prefix;
  }

  format(text: string): string {
    return this.prefix + text.replace(pattern, "") + add(1, 2);
  }

  static create(): Formatter {
    return new Formatter(Formatter.defaultPrefix);
  }

  get label(): string {
    return this.prefix;
  }

  render = (settings: Settings) => this.prefix + settings.url;
}

export const fakeTemplate = template;
