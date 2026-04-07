import { Fragment } from 'react';

export const PaletteTree = () => (
  <Fragment>
    <ExampleLoaderComponent />
  </Fragment>
);

export function ExampleLoaderComponent() {
  return (
    <Fragment>Loading...</Fragment>
  );
}