import React from "react";
import axios from "axios";

import Button from "react-bootstrap/Button";

const API_BASE_URL = "http://172.30.1.27:8006/";

const handleClickFactory = (urlSuffix, album, setTitle) => {
  const handleClick = (event) => {
    axios
      .put(`${API_BASE_URL}album/${album.id}/${urlSuffix}`)
      .then(function (response) {
        setTitle(<mark>{album.title}</mark>);
      })
      .catch(function (error) {
        setTitle(<s>{album.title}</s>);
      });
  };

  return handleClick;
};

const AddAction = ({ album, setTitle, isDisabled }) => {
  const handleClick = handleClickFactory("add", album, setTitle);
  return (
    <Button variant="primary" onClick={handleClick} disabled={isDisabled}>
      Add
    </Button>
  );
};

const RemoveAction = ({ album, setTitle }) => {
  const handleClick = handleClickFactory("remove", album, setTitle);
  return (
    <Button variant="primary" onClick={handleClick}>
      Remove
    </Button>
  );
};

const DownloadAction = ({ album, setTitle }) => {
  const handleClick = handleClickFactory("download", album, setTitle);
  return (
    <Button variant="primary" onClick={handleClick}>
      Download
    </Button>
  );
};

const UploadAction = ({ album, setTitle }) => {
  const handleClick = handleClickFactory("upload", album, setTitle);
  return (
    <Button variant="primary" onClick={handleClick}>
      Upload
    </Button>
  );
};

export { AddAction, DownloadAction, UploadAction, RemoveAction };
