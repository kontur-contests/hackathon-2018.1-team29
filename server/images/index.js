"use strict";

require("dotenv").config({path: require("path").join(__dirname, process.argv[2])});

const express = require("express");
const errorHandler = require('errorhandler');
const { Pool } = require('pg');

var app = express();

app.set("x-powered-by", false);
if (process.env.TRUST_PROXY)
  app.set("trust proxy", process.env.TRUST_PROXY); 

app.get("/:id", async (req, res, next) => {
  const db = new Pool();
  const { id } = req.params;
  var rows;
  try {
    rows = await db.query('SELECT mimetype, image_content FROM images WHERE id = $1', [id]);
  }
  catch(e) {
    return next(e);
  }
  rows = rows.rows;
  if (rows.length < 1)
    return next();
  res.set('Content-Type', rows[0].mimetype);
  return res.send(rows[0].image_content);
});

if (process.env.NODE_ENV === "production") {
  app.use(function(req, res, next) {
    var err = new Error('Not Found');
    err.status = 404;
    next(err);
  });

  app.use(function(err, req, res, next) {
    res.status(err.status || 500);
    res.send();
  });
}
else if (process.env.NODE_ENV === "development")
  app.use(errorHandler());

app.listen(process.env.PORT, function() {
  console.log(`${process.mainModule.filename} started, pid is ${process.pid}, port is ${process.env.PORT}`);
});
