#!/usr/bin/env python3

import numpy as np
import yarp
import sys
import pickle as pk
import distutils.util
import cv2

from functions.config import IMAGE_HEIGHT, IMAGE_WIDTH, get_keypoints_inds
from functions.utilities import read_openpose_data, get_features
from functions.utilities import draw_on_img, get_human_idx, create_bottle, get_mean_depth_over_area


yarp.Network.init()

class MultiFaceClassifier(yarp.RFModule):

    def configure(self, rf):
        self.model_name = rf.find("model_name").asString()
        print('SVM model file: %s' % self.model_name)
        self.clf = pk.load(open('./src/functions/' + self.model_name, 'rb'))
        self.MAX_FRAMERATE = bool(distutils.util.strtobool((rf.find("max_framerate").asString())))
        print('Max framerate: %s' % str(self.MAX_FRAMERATE))
        self.threshold = rf.find("max_propagation").asInt32()  # to reset the buffer
        print('SVM Buffer threshold: %d' % self.threshold)
        self.buffer = yarp.Bottle()  # each element is ((0, 0), 0, 0, 0) centroid, depth, prediction and level of confidence
        self.counter = 0  # counter for the threshold
        self.svm_buffer_size = 3
        self.svm_buffer = (np.array([], dtype=object)).tolist()
        self.id_image = '%08d' % 0

        self.keypoint_detector = rf.find("keypoint_detector").asString()
        self.JOINTS_POSE, self.JOINTS_FACE = get_keypoints_inds(self.keypoint_detector)
        self.NUM_JOINTS = len(self.JOINTS_POSE) + len(self.JOINTS_FACE)
        self.pose_conf_threshold = rf.find("pose_conf_threshold").asFloat32()
        self.face_conf_threshold = rf.find("face_conf_threshold").asFloat32()

        self.cmd_port = yarp.Port()
        self.cmd_port.open('/mutualgaze/command:i')
        print('{:s} opened'.format('/mutualgaze/command:i'))
        self.attach(self.cmd_port)

        # input port for rgb image
        self.in_port_human_image = yarp.BufferedPortImageRgb()
        self.in_port_human_image.open('/mutualgaze/image:i')
        self.in_buf_human_array = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        self.in_buf_human_image = yarp.ImageRgb()
        self.in_buf_human_image.resize(IMAGE_WIDTH, IMAGE_HEIGHT)
        self.in_buf_human_image.setExternal(self.in_buf_human_array.data, self.in_buf_human_array.shape[1], self.in_buf_human_array.shape[0])
        print('{:s} opened'.format('/mutualgaze/image:i'))

        # input port for depth
        self.in_port_human_depth = yarp.BufferedPortImageFloat()
        self.in_port_human_depth_name = '/mutualgaze/depth:i'
        self.in_port_human_depth.open(self.in_port_human_depth_name)
        self.in_buf_human_depth_array = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 1), dtype=np.float32)
        self.in_buf_human_depth = yarp.ImageFloat()
        self.in_buf_human_depth.resize(IMAGE_WIDTH, IMAGE_HEIGHT)
        self.in_buf_human_depth.setExternal(self.in_buf_human_depth_array.data, self.in_buf_human_depth_array.shape[1], self.in_buf_human_depth_array.shape[0])
        print('{:s} opened'.format('/mutualgaze/depth:i'))

        # input port for openpose data
        self.in_port_human_data = yarp.BufferedPortBottle()
        self.in_port_human_data.open('/mutualgaze/data:i')
        print('{:s} opened'.format('/mutualgaze/data:i'))

        # output port for the prediction
        self.out_port_prediction = yarp.Port()
        self.out_port_prediction.open('/mutualgaze/pred:o')
        print('{:s} opened'.format('/mutualgaze/pred:o'))

        # output port for rgb image
        self.out_port_human_image = yarp.Port()
        self.out_port_human_image.open('/mutualgaze/image:o')
        self.out_buf_human_array = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        self.out_buf_human_image = yarp.ImageRgb()
        self.out_buf_human_image.resize(IMAGE_WIDTH, IMAGE_HEIGHT)
        self.out_buf_human_image.setExternal(self.out_buf_human_array.data, self.out_buf_human_array.shape[1], self.out_buf_human_array.shape[0])
        print('{:s} opened'.format('/mutualgaze/image:o'))

        # propag input image
        self.out_port_propag_image = yarp.Port()
        self.out_port_propag_image.open('/mutualgaze/propag:o')
        self.out_buf_propag_array = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        self.out_buf_propag_image = yarp.ImageRgb()
        self.out_buf_propag_image.resize(IMAGE_WIDTH, IMAGE_HEIGHT)
        self.out_buf_propag_image.setExternal(self.out_buf_propag_array.data, self.out_buf_propag_array.shape[1],
                                              self.out_buf_propag_array.shape[0])
        print('{:s} opened'.format('/mutualgaze/propag:o'))

        self.human_image = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        self.human_image_depth = np.ones((IMAGE_HEIGHT, IMAGE_WIDTH, 1), dtype=np.float32)

        return True

    def respond(self, command, reply):
        if command.get(0).asString() == 'quit':
            print('received command QUIT')
            self.cleanup()
            reply.addString('quit command sent')
        elif command.get(0).asString() == 'get':
            print('received command GET')
            reply.copy(self.buffer)
        else:
            print('Command {:s} not recognized'.format(command.get(0).asString()))
            reply.addString('Command {:s} not recognized'.format(command.get(0).asString()))

        return True

    def cleanup(self):
        print('Cleanup function')
        self.in_port_human_image.close()
        self.in_port_human_data.close()
        self.in_port_human_depth.close()
        self.out_port_human_image.close()
        self.out_port_propag_image.close()
        self.out_port_prediction.close()
        return True

    def interruptModule(self):
        print('Interrupt function')
        self.in_port_human_image.close()
        self.in_port_human_data.close()
        self.in_port_human_depth.close()
        self.out_port_human_image.close()
        self.out_port_propag_image.close()
        self.out_port_prediction.close()
        return True

    def getPeriod(self):
        return 0.001

    def updateModule(self):

        received_image = self.in_port_human_image.read()
        received_depth = self.in_port_human_depth.read(False)  # non blocking

        if received_image:
            self.in_buf_human_image.copy(received_image)
            human_image = np.copy(self.in_buf_human_array)

            self.human_image = np.copy(human_image)
            self.id_image = '%08d' % ((int(self.id_image) + 1) % 100000)

            if received_depth:
                self.in_buf_human_depth.copy(received_depth)
                self.human_image_depth = np.copy(self.in_buf_human_depth_array)

            if self.MAX_FRAMERATE:
                received_data = self.in_port_human_data.read(False)  # non blocking
            else:
                received_data = self.in_port_human_data.read()

            if received_data:
                poses, conf_poses, faces, conf_faces = read_openpose_data(received_data)

                if self.pose_conf_threshold > 0 and self.face_conf_threshold > 0:
                    poses = [pose for pose, conf in zip(poses, conf_poses) if conf.mean() > self.pose_conf_threshold]
                    conf_poses= [conf for conf in conf_poses if conf.mean() > self.pose_conf_threshold]
                    faces = [face for face, conf in zip(faces, conf_faces) if conf.mean() > self.face_conf_threshold]
                    conf_faces= [conf for conf in conf_faces if conf.mean() > self.face_conf_threshold]
                    
                # get features of all people in the image
                data = get_features(poses, conf_poses, faces, conf_faces, self.JOINTS_POSE, self.JOINTS_FACE)

                idx_humans_frame = []
                if data:
                    # predict model
                    # start from 2 because there is the centroid valued in the position [0,1]
                    ld = np.array(data)
                    x = ld[:, 2:(self.NUM_JOINTS * 2) + 2]
                    c = ld[:, (self.NUM_JOINTS * 2) + 2:ld.shape[1]]
                    # weight the coordinates for its confidence value
                    wx = np.concatenate((np.multiply(x[:, ::2], c), np.multiply(x[:, 1::2], c)), axis=1)

                    # return a prob value between 0,1 for each class
                    y_classes = self.clf.predict_proba(wx)

                    output_pred_bottle = yarp.Bottle()
                    for itP in range(0, y_classes.shape[0]):
                        prob = max(y_classes[itP])
                        y_pred = (np.where(y_classes[itP] == prob))[0]

                        min_dist, idx = get_human_idx(self.svm_buffer, ld[itP, 0:2])
                        if (idx != None and min_dist != None) and ((len(self.svm_buffer) == y_classes.shape[0]) or (min_dist < 50)): # suppose min dist < 50 pixels
                            idx_humans_frame.append(idx)
                            if len(self.svm_buffer[idx]) == 3:
                                self.svm_buffer[idx].pop(0)

                            self.svm_buffer[idx].append([ld[itP, 0], ld[itP, 1], y_pred[0], prob])

                            count_class_0 = [(self.svm_buffer[idx])[i][2] for i in range(0, len(self.svm_buffer[idx]))].count(0)
                            count_class_1 = [(self.svm_buffer[idx])[i][2] for i in range(0, len(self.svm_buffer[idx]))].count(1)
                            if count_class_1 == count_class_0:
                                y_winner = y_pred[0]
                                prob_mean = prob
                            else:
                                y_winner = np.argmax([count_class_0, count_class_1])
                                prob_values = np.array([(self.svm_buffer[idx])[i][3] for i in range(0, len(self.svm_buffer[idx])) if (self.svm_buffer[idx])[i][2] == y_winner])
                                prob_mean = np.mean(prob_values)

                        else:
                            self.svm_buffer.append([[ld[itP, 0], ld[itP, 1], y_pred[0], prob]])
                            print("num of humans in the scene: %d" % len(self.svm_buffer))
                            idx_humans_frame.append(len(self.svm_buffer)-1)
                            y_winner = y_pred[0]
                            prob_mean = prob

                        if self.human_image_depth is not None:
                            depth = get_mean_depth_over_area(self.human_image_depth, [int(ld[itP, 0]), int(ld[itP, 1])], 20)
                        else:
                            depth = -1

                        pred = create_bottle((self.id_image, (int(ld[itP,0]), int(ld[itP,1])), depth, y_winner, prob_mean))
                        output_pred_bottle.addList().read(pred)
                        human_image = draw_on_img(human_image, self.id_image, (ld[itP,0], ld[itP,1]), y_winner, prob_mean)

                    self.out_buf_human_array[:, :] = human_image
                    self.out_port_human_image.write(self.out_buf_human_image)
                    self.out_port_prediction.write(output_pred_bottle)
                    # propag received image
                    self.out_buf_propag_array[:, :] = self.human_image
                    self.out_port_propag_image.write(self.out_buf_propag_image)

                    self.buffer.copy(output_pred_bottle)
                    self.counter = 0
                else:
                    # no humans in the scene
                    output_pred_bottle = yarp.Bottle()
                    pred = create_bottle((self.id_image, (), -1, -1, -1))
                    output_pred_bottle.addList().read(pred)
                    # print only the self.id_image
                    human_image = cv2.putText(human_image, 'id: ' + str(self.id_image), tuple([25, 30]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

                    self.out_buf_human_array[:, :] = human_image
                    self.out_port_human_image.write(self.out_buf_human_image)
                    self.out_port_prediction.write(output_pred_bottle)
                    # propag received image
                    self.out_buf_propag_array[:, :] = self.human_image
                    self.out_port_propag_image.write(self.out_buf_propag_image)

                    self.buffer.copy(output_pred_bottle)
                    self.counter = 0

                for i in reversed(range(len(self.svm_buffer))):
                    if not (i in idx_humans_frame):
                        self.svm_buffer.pop(i)
                        print("num of humans in the scene: %d" % len(self.svm_buffer))

            else:
                # branch to increase the framerate, received_data is None
                if self.MAX_FRAMERATE and (self.counter < self.threshold):
                    output_pred_bottle = yarp.Bottle()
                    # send in output the buffer
                    for i in range(0, self.buffer.size()):
                        buffer = self.buffer.get(i).asList()
                        centroid = buffer.get(1).asList()
                        # change id_image in the buffer bottle
                        if centroid.size() != 0:
                            human_image = draw_on_img(human_image, self.id_image, (centroid.get(0).asInt(), centroid.get(1).asInt()), buffer.get(3).asInt(), buffer.get(4).asDouble())
                            pred = create_bottle((self.id_image, (centroid.get(0).asInt(), centroid.get(1).asInt()), buffer.get(2).asDouble(), buffer.get(3).asInt(), buffer.get(4).asDouble()))
                        else:
                            human_image = cv2.putText(human_image, 'id: ' + str(self.id_image), tuple([25, 30]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
                            pred = create_bottle((self.id_image, (), buffer.get(2).asDouble(), buffer.get(3).asInt(), buffer.get(4).asDouble()))

                        output_pred_bottle.addList().read(pred)

                    self.buffer.copy(output_pred_bottle)

                    # write rgb image
                    self.out_buf_human_array[:, :] = human_image
                    self.out_port_human_image.write(self.out_buf_human_image)
                    # write prediction bottle
                    self.out_port_prediction.write(self.buffer)
                    # propag received image
                    self.out_buf_propag_array[:, :] = self.human_image
                    self.out_port_propag_image.write(self.out_buf_propag_image)

                    self.counter = self.counter + 1

        return True


if __name__ == '__main__':

    rf = yarp.ResourceFinder()
    rf.setVerbose(True)
    rf.setDefaultContext("MultiFaceClassifier")
    rf.setDefaultConfigFile('./app/config/classifier_conf.ini')

    rf.configure(sys.argv)

    # Run module
    manager = MultiFaceClassifier()
    manager.runModule(rf)
