import { PaletteTree } from './palette';

const ComponentPreviews = () => {
  return (
    <div className="hidden" aria-hidden="true" data-dev-previews="optional">
      <PaletteTree />
    </div>
  );
};

export default ComponentPreviews;