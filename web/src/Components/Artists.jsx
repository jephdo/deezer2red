import React from "react";

import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Card from "react-bootstrap/Card";
import ListGroup from "react-bootstrap/ListGroup";
import InputGroup from "react-bootstrap/InputGroup";

import Album from "./Album";
import ReviewToolbar from "./ReviewToolbar";
import Paginator from "./Paginator";

const Artists = ({
  artists,
  fetchArtists,
  pageSettings,
  availableActions,
  showToolbar,
}) => {
  return (
    <>
      <Row>
        {" "}
        {artists.map((artist) => (
          <Artist
            key={artist.id}
            artist={artist}
            availableActions={availableActions}
            showToolbar={showToolbar}
          />
        ))}
      </Row>

      <Row className="d-flex justify-content-center">
        <Col className="col-lg-1">
          {" "}
          <Paginator
            page={pageSettings.page}
            pages={pageSettings.pages}
            fetchArtists={fetchArtists}
          />
        </Col>
      </Row>
    </>
  );
};

const Artist = ({ artist, availableActions, showToolbar = false }) => {
  const albums = [...artist.albums].sort(
    (a, b) => -1 * a.release_date.localeCompare(b.release_date)
  );

  const [showArtist, setShowArtist] = React.useState(true);

  if (!showArtist) {
    return;
  }

  const deezerUrl = `https://www.deezer.com/artist/${artist.id}`;

  return (
    <Row className="justify-content-md-center">
      <Col lg="2">
        <Card className="mx-2 my-4">
          <a href={deezerUrl} target="_blank" rel="noopener noreferrer">
            <Card.Img src={artist.image_url} />
          </a>
          <Card.Body>
            <Card.Title>
              {artist.name} <kbd>{artist.id}</kbd>
            </Card.Title>
            <Card.Subtitle>{artist.nb_fan} fans</Card.Subtitle>
          </Card.Body>
        </Card>
      </Col>
      <Col>
        {showToolbar && (
          <Row>
            <div className="mx-2 my-4">
              <ReviewToolbar artist={artist} setShowArtist={setShowArtist} />
            </div>
          </Row>
        )}

        <Row>
          <ListGroup className="my-4" variant="flush">
            {albums.map((album) => (
              <Album
                key={album.id}
                album={album}
                availableActions={availableActions}
              />
            ))}
          </ListGroup>
        </Row>
      </Col>
    </Row>
  );
};

export default Artists;
