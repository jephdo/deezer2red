import React from "react";

import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Card from "react-bootstrap/Card";
import ListGroup from "react-bootstrap/ListGroup";
import InputGroup from "react-bootstrap/InputGroup";

import Album from "./Album";

const Artists = ({ artists }) => {
  return (
    <div>
      {artists.map((artist) => (
        <Artist key={artist.id} artist={artist} />
      ))}
    </div>
  );
};

const Artist = ({ artist }) => {
  const albums = [...artist.albums].sort(
    (a, b) => -1 * a.release_date.localeCompare(b.release_date)
  );

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
        <ListGroup className="my-4" variant="flush">
          {albums.map((album) => (
            <Album key={album.id} album={album} />
          ))}
        </ListGroup>
      </Col>
      <Col lg="3">
        <div className="mx-2 my-4">
          <SearchMatch artist={artist} />
        </div>
      </Col>
    </Row>
  );
};

const SearchMatch = ({ artist }) => {
  const handleSearch = (event) => {
    event.preventDefault();
  };

  const handleReview = (event) => {
    event.preventDefault();
  };

  return (
    <div>
      <Form className="card p-2">
        <InputGroup>
          <Form.Control
            type="text"
            value={artist.name}
            aria-label="Input group example"
            aria-describedby="btnGroupAddon"
          />
          <Button variant="secondary" type="submit" onClick={handleSearch}>
            Search
          </Button>
          <Button variant="danger" type="submit" onClick={handleReview}>
            Reviewed
          </Button>
        </InputGroup>
      </Form>
    </div>
  );
};

export default Artists;
