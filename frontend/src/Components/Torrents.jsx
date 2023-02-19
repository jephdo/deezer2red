import { React, useEffect, useState } from "react";
import axios from "axios";

const API_ENDPOINT = "http://localhost:8006";

const Torrents = () => {
  const [torrents, setTorrents] = useState([]);
  const fetchTorrents = () => {
    axios.get(API_ENDPOINT).then((response) => {
      setTorrents(response.data);
    });
  };

  useEffect(() => {
    fetchTorrents();
  }, []);

  return (
    <>
      <div>{torrents}</div>
    </>
  );
};

export default Torrents;
