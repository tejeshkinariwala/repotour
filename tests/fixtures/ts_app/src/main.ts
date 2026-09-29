import { readFileSync } from "node:fs";
import express from "express";
import { render } from "@scope/pkg/deep";
import Page from "./components/Button";

const handlers = {
  start: startServer,
  stop: stopServer,
};

function startServer() {
  return [readFileSync, express, render, Page];
}

function stopServer() {
  return null;
}

export default handlers;
