import React from "react";

import Badge from "react-bootstrap/Badge";
import ButtonGroup from "react-bootstrap/ButtonGroup";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Image from "react-bootstrap/Image";
import ListGroup from "react-bootstrap/ListGroup";

import {
  AddAction,
  UploadAction,
  DownloadAction,
  RemoveAction,
} from "./Actions";

const Album = ({
  album,
  availableActions: { addAction, downloadAction, uploadAction, removeAction },
}) => {
  const pillBg = (() => {
    switch (album.record_type) {
      case "album":
        return "primary";
      case "ep":
        return "success";
      case "single":
        return "secondary";
      default:
        return "danger";
    }
  })();
  const deezerUrl = `https://www.deezer.com/album/${album.id}`;
  const isDisabled = album.ready_to_add;
  const [title, setTitle] = React.useState(album.title);

  return (
    <ListGroup.Item>
      <div className="ms-2 me-auto">
        <Row>
          <Col lg="2">
            <a href={deezerUrl} target="_blank" rel="noopener noreferrer">
              <Image src={album.image_url} thumbnail />
            </a>
          </Col>
          <Col lg="6">
            {" "}
            <div className="fw-bold">
              {title}{" "}
              <Badge pill bg={pillBg}>
                {album.record_type}
              </Badge>{" "}
            </div>
            <div>
              <span>
                <kbd>{album.id}</kbd>
              </span>{" "}
              | <span>{album.release_date}</span>
            </div>
          </Col>
          <Col lg="4">
            <ButtonGroup>
              {addAction && (
                <AddAction
                  album={album}
                  setTitle={setTitle}
                  isDisabled={isDisabled}
                />
              )}
              {removeAction && (
                <RemoveAction
                  album={album}
                  setTitle={setTitle}
                  isDisabled={isDisabled}
                />
              )}
              {downloadAction && (
                <DownloadAction album={album} setTitle={setTitle} />
              )}
              {uploadAction && (
                <UploadAction album={album} setTitle={setTitle} />
              )}
            </ButtonGroup>
          </Col>
        </Row>
      </div>
    </ListGroup.Item>
  );
};

export default Album;
